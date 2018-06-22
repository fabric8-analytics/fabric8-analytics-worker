"""Task to analyze vulnerable packages and mark them in graph as such."""


from f8a_worker.base import BaseTask
from f8a_worker.models import Ecosystem
from f8a_worker.victims import VictimsDB
from f8a_worker.graphutils import update_properties
from selinon import run_flow, StoragePool


class VictimsCheck(BaseTask):
    """Victims CVE Check task."""

    def execute(self, arguments):
        """Task to analyze vulnerable packages and mark them in graph as such.

        :param arguments: dictionary with task arguments
        :return: None
        """
        self._strict_assert(arguments.get('ecosystem'))

        rdb = StoragePool.get_connected_storage('BayesianPostgres')
        ecosystem = Ecosystem.by_name(rdb.session, arguments.get('ecosystem'))

        with VictimsDB.build_from_git() as db:

            self.log.info('Storing the VictimsDB zip on S3')
            db.store_on_s3()

            vulnerable_packages = self.get_vulnerable_packages(db, ecosystem)
            self.analyze_vulnerable_components(vulnerable_packages, ecosystem)

            self.mark_in_graph(vulnerable_packages, ecosystem)

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

    def analyze_vulnerable_components(self, vulnerable_packages, ecosystem):
        """Make sure we have all packages with known vulnerabilities ingested.

        Runs non-forced bayesianPriorityFlow analysis.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem
        :return: None
        """
        for ga, data in vulnerable_packages.items():
            if data:
                versions = data[0].get('affected', []) + data[0].get('not_affected', [])
                for version in versions:
                    node_args = {
                        'ecosystem': ecosystem.name,
                        'force': False,
                        'force_graph_sync': False,
                        'name': ga,
                        'recursive_limit': 0,
                        'version': version
                    }
                    self.log.info("Scheduling analysis of a package "
                                  "with known vulnerabilities: {ga}:{v}".format(ga=ga, v=version))
                    run_flow('bayesianPriorityFlow', node_args)

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
