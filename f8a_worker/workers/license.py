"""
Uses ScanCode toolkit to detect licences in source code.
"""

from os import getenv, path
from f8a_worker.utils import TimedCommand, username
from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef
from f8a_worker.object_cache import ObjectCache
from selinon import FatalTaskError


class LicenseCheckTask(BaseTask):
    """ Check licences of all files of a package """
    _analysis_name = 'source_licenses'
    schema_ref = SchemaRef(_analysis_name, '3-0-0')

    SCANCODE_LICENSE_SCORE = getenv('SCANCODE_LICENSE_SCORE', '20')  # scancode's default is 0
    SCANCODE_TIMEOUT = getenv('SCANCODE_TIMEOUT', '120')  # scancode's default is 120
    SCANCODE_PROCESSES = getenv('SCANCODE_PROCESSES', '1')  # scancode's default is 1
    SCANCODE_IGNORE = ['*.pyc', '*.so', '*.dll', '*.rar', '*.jar',
                       '*.zip', '*.tar', '*.tar.gz', '*.tar.xz']  # don't scan binaries

    @staticmethod
    def process_output(data):
        # not interested in these
        keys_to_remove = ['start_line', 'end_line', 'matched_rule', 'score', 'key']
        # 'files' is a list of file paths along with info about detected licenses.
        # If there's the same license text in most files, then almost the same license info
        # accompanies each file path.
        # Therefore transform it into dict of licenses (keys) along with info about the license plus
        # paths of files where the license has been detected.
        licenses = {}
        for file in data.pop('files'):
            for _license in file['licenses']:
                # short_name becomes key
                short_name = _license.pop('short_name')
                if short_name not in licenses.keys():
                    for key in keys_to_remove:
                        del _license[key]
                    _license['paths'] = {file['path']}
                    licenses[short_name] = _license
                else:
                    licenses[short_name]['paths'].add(file['path'])
        for l in licenses.values():
            l['paths'] = list(l['paths'])  # set -> list
        data['licenses'] = licenses

        del data['scancode_options']
        return data

    @staticmethod
    def run_scancode(scan_path):
        result_data = {'status': 'unknown',
                       'summary': {},
                       'details': {}}
        command = [path.join(getenv('SCANCODE_PATH', '/opt/scancode-toolkit/'),
                             'scancode'),
                   # Scan for licenses
                   '--license',
                   # Do not return license matches with scores lower than this score
                   '--license-score', LicenseCheckTask.SCANCODE_LICENSE_SCORE,
                   # Files without findings are omitted
                   '--only-findings',
                   # Use n parallel processes
                   '--processes', LicenseCheckTask.SCANCODE_PROCESSES,
                   # Do not print summary or progress messages
                   '--quiet',
                   # Strip the root directory segment of all paths
                   '--strip-root',
                   # Stop scanning a file if scanning takes longer than a timeout in seconds
                   '--timeout', LicenseCheckTask.SCANCODE_TIMEOUT,
                   scan_path]
        for ignore_pattern in LicenseCheckTask.SCANCODE_IGNORE:
            command += ['--ignore', '{}'.format(ignore_pattern)]
        with username():
            tc = TimedCommand(command)
            status, output, error = tc.run(is_json=True, timeout=1200)
            if status != 0:
                raise FatalTaskError("Error (%s) during running command %s: %r" %
                                     (str(status), command, error))

        details = LicenseCheckTask.process_output(output)
        result_data['details'] = details
        result_data['status'] = 'success'
        result_data['summary'] = {'sure_licenses': list(details['licenses'].keys())}

        return result_data

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))
        eco = arguments['ecosystem']
        pkg = arguments['name']
        ver = arguments['version']

        try:
            cache_path = ObjectCache.get_from_dict(arguments).get_sources()
        except Exception:
            if arguments['ecosystem'] != 'maven':
                self.log.error('Could not get sources for package {e}/{p}/{v}'.
                               format(e=eco, p=pkg, v=ver))
                raise
            self.log.info('Could not get sources for maven package {p}/{v},'
                          'will try to run on binary jar'.format(p=pkg, v=ver))
            cache_path = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()

        result_data = self.run_scancode(cache_path)
        return result_data
