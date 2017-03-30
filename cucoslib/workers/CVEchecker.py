import anymarkup
import os
from selinon import StoragePool
from cucoslib.base import BaseTask
from cucoslib.object_cache import ObjectCache
from cucoslib.schemas import SchemaRef
from cucoslib.solver import get_ecosystem_solver
from cucoslib.utils import get_command_output, tempdir


class CVEcheckerTask(BaseTask):
    name = 'cucoslib.workers.CVEchecker'
    _analysis_name = 'security_issues'
    description = "Security issues scanner. Uses Snyk vulndb for npm and OWASP Dep.Check for maven"
    schema_ref = SchemaRef(_analysis_name, '3-0-0')

    @staticmethod
    def _filter_vulndb_fields(entry):
        result = {
            'cvss': {
                'score': 0,
                'vector': ""
            }
        }
        for field in ['description', 'severity']:
            result[field] = entry.get(field)
        id = entry.get('identifiers', {}).get('CVE') or entry.get('identifiers', {}).get('CWE')
        result['id'] = id[0] if id else ''
        # prefer CVSSv2, because CVSSv3 seems to contain only vector string, not score itself
        if entry.get('CVSSv2'):
            # "CVSSv2": "7.5 (HIGH) (AV:N/AC:L/Au:N/C:P/I:P/A:P)"
            try:
                score, severity, vector = entry.get('CVSSv2').split(' ')
                score = int(score)
                vector = vector.strip('()')
            except ValueError:
                pass
            else:
                result['cvss']['score'] = score
                result['cvss']['vector'] = vector
        elif entry.get('CVSSv3'):
            # "CVSSv3": "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" <- there's no score ??
            result['cvss']['score'] = 0  # ?
            result['cvss']['vector'] = entry.get('CVSSv3')
        # Snyk vulndb doesn't contain references
        result['references'] = []
        return result

    def _npm_scan(self, arguments):
        s3 = StoragePool.get_connected_storage('S3Snyk')

        try:
            self.log.debug('Retrieving Snyk vulndb from S3')
            vulndb = s3.retrieve_vulndb()
        except:
            self.log.error('Failed to obtain Snyk vulndb database')
            return {'summary': ['Failed to obtain Snyk vulndb database'],
                    'status': 'error',
                    'details': []}

        entries = []
        solver = get_ecosystem_solver(self.storage.get_ecosystem('npm'))
        for entry in vulndb.get('npm', {}).get(arguments['name'], []):
            vulnerable_versions = entry['semver']['vulnerable']
            affected_versions = solver.solve(["{} {}".format(arguments['name'],
                                                             vulnerable_versions)],
                                             all_versions=True)
            if arguments['version'] in affected_versions.get(arguments['name'], []):
                entries.append(self._filter_vulndb_fields(entry))

        return {'summary': [e['id'] for e in entries if e],
                'status': 'success',
                'details': entries}

    def _maven_scan(self, arguments):
        jar = ObjectCache.get_from_dict(arguments).get_source_tarball()
        s3 = StoragePool.get_connected_storage('S3OWASPDepCheck')
        s3.retrieve_depcheck_db_if_exists()
        depcheck = os.path.join(os.environ['OWASP_DEP_CHECK_PATH'], 'bin', 'dependency-check.sh')
        with tempdir() as report_dir:
            report_path = os.path.join(report_dir, 'report.xml')
            self.log.debug('Running OWASP Dependency-Check to scan %s for vulnerabilities' % jar)
            get_command_output([depcheck, '--format', 'XML', '--project', 'test', '--scan', jar,
                                '--out', report_path])
            with open(report_path) as r:
                report_dict = anymarkup.parse(r.read())

        results = []
        dependencies = report_dict.get('analysis', {}).get('dependencies', {}).get('dependency', [])
        if not isinstance(dependencies, list):
            dependencies = [dependencies]
        for dependency in dependencies:
            vulnerabilities = dependency.get('vulnerabilities', {}).get('vulnerability', [])
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
                vector = "AV:{AV}/AC:{AC}/Au:{Au}/C:{C}/I:{I}/A:{A}".\
                    format(AV=av, AC=ac, Au=au, C=c, I=i, A=a)
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

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        if arguments['ecosystem'] == 'npm':
            return self._npm_scan(arguments)
        elif arguments['ecosystem'] == 'maven':
            return self._maven_scan(arguments)
        else:
            return {'summary': 'Unsupported ecosystem',
                    'status': 'error',
                    'details': []}
