"""Task to analyze vulnerable packages and mark them in graph as such."""


from f8a_worker.base import BaseTask
from f8a_worker.victims import VictimsDB
from f8a_worker.graphutils import update_properties
from selinon import run_flow


class VictimsCheck(BaseTask):
    """Victims CVE Check task.

    Only for Maven at the moment.
    """

    def execute(self, arguments):
        """Task to analyze vulnerable packages and mark them in graph as such.

        :param arguments: dictionary with task arguments
        :return: None
        """
        with VictimsDB.build_from_git() as db:

            self.log.info('Storing the VictimsDB zip on S3')
            db.store_on_s3()

            vulnerable_packages = self.get_vulnerable_packages(db)
            self.analyze_vulnerable_components(vulnerable_packages)

            self.mark_in_graph(vulnerable_packages)

    def get_vulnerable_packages(self, db):
        """Get vulnerable packages.

        Constructs a dict where keys are package names
        and values are details about vulnerabilities.

        :param db: VictimsDB
        :return: dict, a dict of vulnerable packages with details
        """
        vulnerable_packages = {}
        for pkg in db.get_vulnerable_java_packages():
            ga = pkg['package']
            ga_data = vulnerable_packages.get(ga, [])
            ga_data.append(pkg)
            vulnerable_packages[ga] = ga_data
        return vulnerable_packages

    def analyze_vulnerable_components(self, vulnerable_packages):
        """Make sure we have all packages with known vulnerabilities ingested.

        Runs non-forced bayesianPriorityFlow analysis.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
        :return: None
        """
        for ga, data in vulnerable_packages.items():
            if data:
                versions = data[0].get('affected', []) + data[0].get('not_affected', [])
                for version in versions:
                    node_args = {
                        'ecosystem': 'maven',
                        'force': False,
                        'force_graph_sync': False,
                        'name': ga,
                        'recursive_limit': 0,
                        'version': version
                    }
                    self.log.info("Scheduling analysis of a package "
                                  "with known vulnerabilities: {ga}:{v}".format(ga=ga, v=version))
                    run_flow('bayesianPriorityFlow', node_args)

    def mark_in_graph(self, vulnerable_packages):
        """Mark vulnerable components in graph.

        :param vulnerable_packages: dict, a dict of vulnerable packages with details
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
                update_properties('maven', ga, version, properties)
