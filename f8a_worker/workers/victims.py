"""Task to analyze vulnerable packages and mark them in graph as such."""

import os
import requests

from f8a_worker.base import BaseTask
from f8a_worker.models import Ecosystem
from f8a_worker.victims import VictimsDB, FilteredVictimsDB
from f8a_worker.graphutils import update_properties, create_nodes
from selinon import StoragePool


class VictimsCheck(BaseTask):
    """Victims CVE Check task."""

    def execute(self, arguments):
        """Task to mark vulnerable packages in graph.

        :param arguments: dictionary with task arguments
        :return: None
        """
        self._strict_assert(arguments.get('ecosystem'))

        wanted_cves = set(arguments.get('cve_filter', []))
        victims_cls = VictimsDB if not wanted_cves else FilteredVictimsDB

        rdb = StoragePool.get_connected_storage('BayesianPostgres')
        ecosystem = Ecosystem.by_name(rdb.session, arguments.get('ecosystem'))

        with victims_cls.build_from_git(wanted=wanted_cves) as db:

            self.log.info('Storing the VictimsDB zip on S3')
            db.store_on_s3()

            vulnerable_packages = self.get_vulnerable_packages(db, ecosystem)
            self.create_in_graph(vulnerable_packages, ecosystem)

            self.mark_in_graph(vulnerable_packages, ecosystem)

            self.notify_gemini(vulnerable_packages, ecosystem)

    def init_auth_sa_token(self):
        """Generate service token for authentication."""
        auth_server_url = os.getenv('F8A_AUTH_SERVICE_HOST', '')

        if auth_server_url:
            endpoint = '{url}/api/token'.format(url=auth_server_url)

            client_id = os.getenv('GEMINI_SA_CLIENT_ID', 'id')
            client_secret = os.getenv('GEMINI_SA_CLIENT_SECRET', 'secret')

            payload = {"grant_type": "client_credentials",
                       "client_id": client_id.strip(),
                       "client_secret": client_secret.strip()}

            try:
                self.log.info('Starting token generation using {url} and {payload}'
                              .format(url=endpoint, payload=payload))
                response = requests.post(endpoint, json=payload)
                self.log.info('Response status is {status_code}'
                              .format(status_code=response.status_code))

            except requests.exceptions.RequestException as e:
                raise e

            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                if access_token:
                    self.log.info('Access token successfully generated')
                    return access_token

        raise requests.exceptions.RequestException

    def get_vulnerable_packages(self, db, ecosystem):
        """Get vulnerable packages.

        Constructs a dict where keys are package names
        and values are details about vulnerabilities.

        :param db: VictimsDB
        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem object
        :return: dict, a dict of vulnerable packages with details
        """
        vulnerable_packages = {}
        for pkg in db.get_details_for_ecosystem(ecosystem):
            ga = pkg['package']
            ga_data = vulnerable_packages.get(ga, [])
            ga_data.append(pkg)
            vulnerable_packages[ga] = ga_data
        return vulnerable_packages

    def notify_gemini(self, vulnerable_packages, ecosystem):
        """Notify gemini service about vulnerabilities in packages.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem
        :return: None
        """
        try:
            access_token = self.init_auth_sa_token()
        except requests.exceptions.RequestException as e:
            self.log.error('Access token retrieval failed due to {}'
                           .format(e))
            return

        gemini_url = 'http://{host}:{port}/api/v1/user-repo/notify'.format(
            host=os.environ.get('F8A_GEMINI_SERVER_SERVICE_HOST'),
            port=os.environ.get('F8A_GEMINI_SERVER_SERVICE_PORT')
        )

        for package, data in vulnerable_packages.items():
            if data:
                versions = data[0].get('affected', []) + data[0].get('not_affected', [])
                epv_list = []
                for version in versions:
                    epv = {
                        'ecosystem': ecosystem.name,
                        'name': package,
                        'version': version,
                    }
                    epv_list.append(epv)

                resp = requests.post(gemini_url, json=epv_list,
                                     headers={'Authorization': access_token})

                if resp.status_code != 200:
                    self.log.error('Failed to notify gemini about vulnerabilities in {e}{p}'.format(
                        e=ecosystem.name,
                        p=package
                    ))

    def create_in_graph(self, vulnerable_packages, ecosystem):
        """Make sure we have all packages with known vulnerabilities in graph.

        We don't need to ingest the packages, we just need to create nodes in graph.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem
        :return: None
        """
        for ga, data in vulnerable_packages.items():
            if data:
                versions = data[0].get('affected', []) + data[0].get('not_affected', [])
                epv_list = []
                for version in versions:
                    epv = {
                        'ecosystem': ecosystem.name,
                        'name': ga,
                        'version': version,
                        'source_repo': ecosystem.name
                    }
                    epv_list.append(epv)
                    self.log.info(
                        "Creating nodes in graph for {ga}:{v}, if they don't exist yet".format(
                            ga=ga, v=version
                        )
                    )
                try:
                    create_nodes(epv_list)
                except RuntimeError:
                    # the error has been logged in the function already;
                    # nothing that we can do here
                    pass

    def mark_in_graph(self, vulnerable_packages, ecosystem):
        """Mark vulnerable components in graph.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem
        :return: None
        """
        packages = {}
        for ga, data in vulnerable_packages.items():
            for vulnerability in data:
                ga = vulnerability.get('package')
                versions = packages.get(ga)
                if versions is None:
                    packages[ga] = versions = {}
                for version in vulnerability.get('affected', []):
                    vulnerabilities = versions.get(version, [])
                    cve_id = vulnerability.get('cve_id')
                    cvss = vulnerability.get('cvss_v2') or vulnerability.get('cvss_v3')
                    if not cvss:
                        self.log.error('No CVSS for {cveid}'.format(cveid=cve_id))
                        continue
                    cve_str = "{cveid}:{score}".format(cveid=cve_id, score=cvss)
                    vulnerabilities.append(cve_str)

                    packages[ga][version] = vulnerabilities

        for ga in packages:
            for version in packages[ga]:
                cves = packages[ga][version]
                properties = [{'name': 'cve_ids', 'value': x} for x in cves]
                self.log.info('Marking {ga}:{v} as vulnerable in graph: {vulns}'.format(
                    ga=ga, v=version, vulns=str(cves))
                )
                update_properties(ecosystem.name, ga, version, properties)
