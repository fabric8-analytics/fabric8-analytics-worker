"""Security issues scanner."""

from bs4 import BeautifulSoup
import requests
from selinon import RequestError
from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef
from f8a_worker.solver import get_ecosystem_solver, OSSIndexDependencyParser
from f8a_worker.victims import VictimsDB


class CVEcheckerTask(BaseTask):
    """Security issues scanner."""

    _analysis_name = 'security_issues'
    schema_ref = SchemaRef(_analysis_name, '3-0-1')

    dependency_check_jvm_mem_limit = '-Xmx768m'

    @staticmethod
    def _parse_severity_and_score(input_tag):
        """Parse BeatifulSoup tag and return CVE's score and severity from it."""
        score, severity = input_tag.text.strip().split()
        return float(score), severity.lower()

    @staticmethod
    def _parse_vector(input_tag):
        """Parse BeatifulSoup tag and return CVE vector from it."""
        vector, *_, = input_tag.text.split()
        return vector.strip().lstrip('(').rstrip(')')

    @staticmethod
    def get_cve_impact(cve_id):
        """Get more details about cve_id from NVD."""
        score = 0
        vector = ''
        severity = ''
        if cve_id:
            url = "https://nvd.nist.gov/vuln/detail/{cve_id}".format(cve_id=cve_id)
            response = requests.get(url)
            if not response.status_code == 200:
                raise IOError('Unable to reach URL: {url}'.format(url=url))

            score_v3 = score_v2 = 0
            severity_v3 = severity_v2 = vector_v3 = vector_v2 = ''
            page = BeautifulSoup(response.text, 'html.parser')
            for tag in page.find_all():
                if tag.attrs.get('data-testid') == 'vuln-cvssv3-base-score-link':
                    score_v3, severity_v3 = CVEcheckerTask._parse_severity_and_score(tag)
                elif tag.attrs.get('data-testid') == 'vuln-cvssv3-vector':
                    # I am prefixing CVSS:3.0 to preserve compatibility
                    vector_v3 = "CVSS:3.0/{}".format(CVEcheckerTask._parse_vector(tag))
                elif tag.attrs.get('data-testid') == 'vuln-cvssv2-base-score-link':
                    score_v2, severity_v2 = CVEcheckerTask._parse_severity_and_score(tag)
                elif tag.attrs.get('data-testid') == 'vuln-cvssv2-vector':
                    vector_v2 = CVEcheckerTask._parse_vector(tag)
            # Prefer CVSS v3.0 over v2
            score = score_v3 or score_v2
            severity = severity_v3 or severity_v2
            vector = vector_v3 or vector_v2

        return score, vector, severity

    @staticmethod
    def _filter_ossindex_fields(entry):
        """Create a result record for ossindex entry."""
        score, vector, severity = CVEcheckerTask.get_cve_impact(entry.get('cve'))
        result = {
            'id': entry.get('cve') or entry.get('title'),
            'description': entry.get('description'),
            'references': entry.get('references'),
            'cvss': {
                'score': score,
                'vector': vector
            },
            'severity': severity
        }
        return result

    @staticmethod
    def _filter_victims_db_entry(entry):
        """Create a result record for ossindex entry."""
        if 'cve' not in entry:
            return None
        _, vector, severity = CVEcheckerTask.get_cve_impact(entry.get('cve'))
        result = {
            'id': 'CVE-' + entry['cve'],
            'description': entry.get('description'),
            'references': entry.get('references'),
            'cvss': {
                'score': entry.get('cvss_v3') or entry.get('cvss_v2'),
                'vector': vector
            },
            'severity': severity,
            'attribution': "https://github.com/victims/victims-cve-db, CC BY-SA 4.0, modified"
        }
        return result

    @staticmethod
    def query_url(url):
        """Query url and return json."""
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _query_ossindex_package(ecosystem, name):
        """Get vulnerabilities for a given package ecosystem:name from OSSIndex."""
        url = "https://ossindex.net/v2.0/package/{pm}/{package}".format(pm=ecosystem, package=name)
        return CVEcheckerTask.query_url(url)

    @staticmethod
    def query_ossindex_vulnerability_fromtill(ecosystem, from_time=0, till_time=-1):
        """From OSSIndex get vulnerabilities which changed between from_time and till_time."""
        # OSS Index uses timestamp in milliseconds
        from_time = int(from_time * 1000)
        till_time = int(till_time * 1000)
        url = "https://ossindex.net/v2.0/vulnerability/pm/{pm}/fromtill/{from_time}/{till_time}".\
            format(pm=ecosystem, from_time=from_time, till_time=till_time)
        packages = []
        while url:
            response = CVEcheckerTask.query_url(url)
            for package in response.get('packages', []):
                for vulnerability in package.get('vulnerabilities', []):
                    # Sanity check:
                    # the response always contains at least one entry, even if it should be empty
                    # (when 'from_time' is higher than 'updated' time of all entries in db)
                    if int(vulnerability.get('updated')) < from_time:
                        package['vulnerabilities'].remove(vulnerability)
                if package.get('vulnerabilities', []):
                    packages.append(package)

            url = response.get('next')
        return packages

    def _query_ossindex(self, arguments):
        """Query OSS Index REST API."""
        entries = {}
        solver = get_ecosystem_solver(self.storage.get_ecosystem(arguments['ecosystem']),
                                      with_parser=OSSIndexDependencyParser())
        for package in self._query_ossindex_package(arguments['ecosystem'], arguments['name']):
            for vulnerability in package.get('vulnerabilities', []):
                for version_string in vulnerability.get('versions', []):
                    try:
                        affected_versions = solver.solve(["{} {}".format(arguments['name'],
                                                                         version_string)],
                                                         all_versions=True)
                    except Exception:
                        self.log.exception("Failed to resolve %r for %s:%s", version_string,
                                           arguments['ecosystem'], arguments['name'])
                        continue
                    if arguments['version'] in affected_versions.get(arguments['name'], []):
                        entry = self._filter_ossindex_fields(vulnerability)
                        if entry.get('id'):
                            entries[entry['id']] = entry

        return {'summary': list(entries.keys()),
                'status': 'success',
                'details': list(entries.values())}

    @staticmethod
    def update_victims_cve_db_on_s3():
        """Update Victims CVE DB on S3."""
        with VictimsDB.build_from_git() as db:
            db.store_on_s3()

    def _query_victims(self, arguments, ecosystem):
        """Check EPV with VictimsDB."""
        db = None
        try:
            db = VictimsDB.from_s3()
            if not db:
                self.log.debug('No Victims CVE DB found on S3, cloning from github')
                db = VictimsDB.build_from_git()
                db.store_on_s3()

            return db.get_vulnerabilities_for_epv(ecosystem,
                                                  arguments['name'],
                                                  arguments['version'])
        finally:
            if db:
                db.close()

    def _victims_scan(self, arguments, ecosystem):
        """Run Victims CVE DB CLI."""
        results = {
            'summary': [],
            'status': 'success',
            'details': []
        }
        victims_cve_db_results = self._query_victims(arguments, ecosystem)
        for vulnerability in victims_cve_db_results:
            vulnerability = self._filter_victims_db_entry(vulnerability)
            if not vulnerability:
                continue
            if vulnerability['id'] not in results['summary']:
                results['summary'].append(vulnerability['id'])
                results['details'].append(vulnerability)
        return results

    def _nuget_scan(self, arguments):
        """Get vulnerabilities info about given nuget package."""
        return self._query_ossindex(arguments)

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        if arguments['ecosystem'] in ('maven', 'pypi', 'npm'):
            return self._victims_scan(arguments, arguments['ecosystem'])
        elif arguments['ecosystem'] == 'nuget':
            return self._nuget_scan(arguments)
        else:
            raise RequestError('Unsupported ecosystem')
