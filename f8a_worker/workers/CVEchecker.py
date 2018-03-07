"""Security issues scanner."""

import anymarkup
from bs4 import BeautifulSoup
from glob import glob
import os
from re import compile as re_compile
import requests
from shutil import rmtree, copy
from tempfile import gettempdir, TemporaryDirectory
from selinon import StoragePool, FatalTaskError, RequestError
from f8a_worker.base import BaseTask
from f8a_worker.defaults import configuration
from f8a_worker.errors import TaskError
from f8a_worker.object_cache import ObjectCache
from f8a_worker.process import Git
from f8a_worker.schemas import SchemaRef
from f8a_worker.solver import get_ecosystem_solver, OSSIndexDependencyParser
from f8a_worker.utils import TimedCommand


class CVEcheckerTask(BaseTask):
    """Security issues scanner."""

    _analysis_name = 'security_issues'
    schema_ref = SchemaRef(_analysis_name, '3-0-1')

    dependency_check_jvm_mem_limit = '-Xmx768m'

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
            for tag in page.find_all(href=re_compile('calculator')):
                if tag.attrs.get('data-testid') == 'vuln-cvssv3-base-score-link':
                    score_v3 = float(tag.text.strip())
                    severity_v3 = tag.find_next().text.lower()
                elif tag.attrs.get('data-testid') == 'vuln-cvssv3-vector-link':
                    vector_v3 = tag.text.strip()
                elif tag.attrs.get('data-testid') == 'vuln-cvssv2-base-score-link':
                    score_v2 = float(tag.text.strip())
                    severity_v2 = tag.find_next().text.lower()
                elif tag.attrs.get('data-testid') == 'vuln-cvssv2-vector-link':
                    vector_v2 = tag.text.strip().lstrip('(').rstrip(')')
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

    def _npm_scan(self, arguments):
        """Get vulnerabilities info about given npm package."""
        return self._query_ossindex(arguments)

    @staticmethod
    def update_depcheck_db_on_s3():
        """Update OWASP Dependency-check DB on S3."""
        s3 = StoragePool.get_connected_storage('S3VulnDB')
        depcheck = configuration.dependency_check_script_path
        with TemporaryDirectory() as temp_data_dir:
            s3.retrieve_depcheck_db_if_exists(temp_data_dir)
            old_java_opts = os.getenv('JAVA_OPTS', '')
            os.environ['JAVA_OPTS'] = CVEcheckerTask.dependency_check_jvm_mem_limit
            # give DependencyCheck 25 minutes to download the DB
            if TimedCommand.get_command_output([depcheck, '--updateonly', '--data', temp_data_dir],
                                               timeout=1500):
                s3.store_depcheck_db(temp_data_dir)
            os.environ['JAVA_OPTS'] = old_java_opts

    def _run_owasp_dep_check(self, scan_path, experimental=False):
        """Run OWASP Dependency-Check."""
        def _clean_dep_check_tmp():
            for dcdir in glob(os.path.join(gettempdir(), 'dctemp*')):
                rmtree(dcdir)

        s3 = StoragePool.get_connected_storage('S3VulnDB')
        depcheck = configuration.dependency_check_script_path
        with TemporaryDirectory() as temp_data_dir:
            if not s3.retrieve_depcheck_db_if_exists(temp_data_dir):
                self.log.debug('No cached OWASP Dependency-Check DB, generating fresh now ...')
                self.update_depcheck_db_on_s3()
                s3.retrieve_depcheck_db_if_exists(temp_data_dir)

            report_path = os.path.join(temp_data_dir, 'report.xml')
            command = [depcheck,
                       '--noupdate',
                       '--format', 'XML',
                       '--project', 'CVEcheckerTask',
                       '--data', temp_data_dir,
                       '--scan', scan_path,
                       '--out', report_path]
            if experimental:
                command.extend(['--enableExperimental'])
            for suppress_xml in glob(os.path.join(os.environ['OWASP_DEP_CHECK_SUPPRESS_PATH'],
                                                  '*.xml')):
                command.extend(['--suppress', suppress_xml])

            output = []
            old_java_opts = os.getenv('JAVA_OPTS', '')
            try:
                self.log.debug('Running OWASP Dependency-Check to scan %s for vulnerabilities' %
                               scan_path)
                os.environ['JAVA_OPTS'] = CVEcheckerTask.dependency_check_jvm_mem_limit
                output = TimedCommand.get_command_output(command,
                                                         graceful=False,
                                                         timeout=600)  # 10 minutes
                with open(report_path) as r:
                    report_dict = anymarkup.parse(r.read())
            except (TaskError, FileNotFoundError) as e:
                _clean_dep_check_tmp()
                for line in output:
                    self.log.warning(line)
                self.log.exception(str(e))
                raise FatalTaskError('OWASP Dependency-Check scan failed') from e
            finally:
                os.environ['JAVA_OPTS'] = old_java_opts
            _clean_dep_check_tmp()

        results = []
        dependencies = report_dict.get('analysis', {}).get('dependencies')  # value can be None
        dependencies = dependencies.get('dependency', []) if dependencies else []
        if not isinstance(dependencies, list):
            dependencies = [dependencies]
        for dependency in dependencies:
            vulnerabilities = dependency.get('vulnerabilities')  # value can be None
            vulnerabilities = vulnerabilities.get('vulnerability', []) if vulnerabilities else []
            if not isinstance(vulnerabilities, list):
                vulnerabilities = [vulnerabilities]
            for vulnerability in vulnerabilities:
                av = vulnerability.get('cvssAccessVector')
                av = av[0] if av else '?'
                ac = vulnerability.get('cvssAccessComplexity')
                ac = ac[0] if ac else '?'
                au = vulnerability.get('cvssAuthenticationr')
                au = au[0] if au else '?'
                c = vulnerability.get('cvssConfidentialImpact')
                c = c[0] if c else '?'
                i = vulnerability.get('cvssIntegrityImpact')
                i = i[0] if i else '?'
                a = vulnerability.get('cvssAvailabilityImpact')
                a = a[0] if a else '?'
                vector = "AV:{AV}/AC:{AC}/Au:{Au}/C:{C}/I:{Integrity}/A:{A}".\
                    format(AV=av, AC=ac, Au=au, C=c, Integrity=i, A=a)
                result = {
                    'cvss': {
                        'score': vulnerability.get('cvssScore'),
                        'vector': vector
                    }
                }
                references = vulnerability.get('references', {}).get('reference', [])
                if not isinstance(references, list):
                    references = [references]
                result['references'] = [r.get('url') for r in references]
                for field in ['severity', 'description']:
                    result[field] = vulnerability.get(field)
                result['id'] = vulnerability.get('name')
                results.append(result)

        return {'summary': [r['id'] for r in results],
                'status': 'success',
                'details': results}

    @staticmethod
    def update_victims_cve_db_on_s3():
        """Update Victims CVE DB on S3."""
        repo_url = 'https://github.com/victims/victims-cve-db.git'
        s3 = StoragePool.get_connected_storage('S3VulnDB')
        with TemporaryDirectory() as temp_dir:
            Git.clone(repo_url, temp_dir, depth="1")
            s3.store_victims_db(temp_dir)

    def _run_victims_cve_db_cli(self, arguments):
        """Run Victims CVE DB CLI."""
        s3 = StoragePool.get_connected_storage('S3VulnDB')
        output = []

        with TemporaryDirectory() as temp_victims_db_dir:
            if not s3.retrieve_victims_db_if_exists(temp_victims_db_dir):
                self.log.debug('No Victims CVE DB found on S3, cloning from github')
                self.update_victims_cve_db_on_s3()
                s3.retrieve_victims_db_if_exists(temp_victims_db_dir)

            try:
                cli = os.path.join(temp_victims_db_dir, 'victims-cve-db-cli.py')
                command = [cli, 'search',
                           '--ecosystem', 'java',
                           '--name', arguments['name'],
                           '--version', arguments['version']]
                output = TimedCommand.get_command_output(command,
                                                         graceful=False,
                                                         is_json=True,
                                                         timeout=60)  # 1 minute
            except TaskError as e:
                self.log.exception(e)

        return output

    def _maven_scan(self, arguments):
        """Run OWASP dependency-check & Victims CVE DB CLI."""
        jar_path = ObjectCache.get_from_dict(arguments).get_source_tarball()
        results = self._run_owasp_dep_check(jar_path, experimental=False)
        if results.get('status') != 'success':
            return results
        # merge with Victims CVE DB results
        victims_cve_db_results = self._run_victims_cve_db_cli(arguments)
        for vulnerability in victims_cve_db_results:
            vulnerability = self._filter_victims_db_entry(vulnerability)
            if not vulnerability:
                continue
            if vulnerability['id'] not in results['summary']:
                results['summary'].append(vulnerability['id'])
                results['details'].append(vulnerability)
        return results

    def _python_scan(self, arguments):
        """Run OWASP dependency-check experimental analyzer for Python artifacts.

        https://jeremylong.github.io/DependencyCheck/analyzers/python.html
        """
        extracted_tarball = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()
        # depcheck needs to be pointed to a specific file, we can't just scan whole directory
        egg_info = pkg_info = metadata = None
        for root, _, files in os.walk(extracted_tarball):
            if root.endswith('.egg-info') or root.endswith('.dist-info'):
                egg_info = root
            if 'PKG-INFO' in files:
                pkg_info = os.path.join(root, 'PKG-INFO')
            if 'METADATA' in files:
                metadata = os.path.join(root, 'METADATA')
        scan_path = egg_info or pkg_info or metadata
        if pkg_info and not egg_info:
            # Work-around for dependency-check ignoring PKG-INFO outside .dist-info/
            # https://github.com/jeremylong/DependencyCheck/issues/896
            egg_info_dir = os.path.join(extracted_tarball, arguments['name'] + '.egg-info')
            try:
                os.mkdir(egg_info_dir)
                copy(pkg_info, egg_info_dir)
                scan_path = egg_info_dir
            except os.error:
                self.log.warning('Failed to copy %s to %s', pkg_info, egg_info_dir)

        if not scan_path:
            raise FatalTaskError('File types not supported by OWASP dependency-check')

        return self._run_owasp_dep_check(scan_path, experimental=True)

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

        if arguments['ecosystem'] == 'maven':
            return self._maven_scan(arguments)
        elif arguments['ecosystem'] == 'npm':
            return self._npm_scan(arguments)
        elif arguments['ecosystem'] == 'pypi':
            return self._python_scan(arguments)
        elif arguments['ecosystem'] == 'nuget':
            return self._nuget_scan(arguments)
        else:
            raise RequestError('Unsupported ecosystem')
