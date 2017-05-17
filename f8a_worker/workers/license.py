"""
Check licences of all files of a package

Uses oslc and a matches against a list from Pelc

Output: list of detected licenses

"""

from f8a_worker.utils import TimedCommand
from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef
from f8a_worker.object_cache import ObjectCache


class LicenseCheckTask(BaseTask):
    _analysis_name = 'source_licenses'
    description = "Check licences of all files of a package"
    schema_ref = SchemaRef(_analysis_name, '2-0-0')

    def execute(self, arguments):
        """
        task code

        :param arguments: dictionary with arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        try:
            cache_path = ObjectCache.get_from_dict(arguments).get_sources()
        except Exception as e:
            eco = arguments.get('ecosystem')
            pkg = arguments.get('name')
            ver = arguments.get('version')
            if arguments['ecosystem'] != 'maven':
                self.log.error('Could not get sources for package {e}/{p}/{v}'.
                               format(e=eco, p=pkg, v=ver))
                raise
            self.log.info('Could not get sources for maven package {p}/{v},'
                          'will try to run on binary jar'.format(p=pkg, v=ver))
            cache_path = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()

        result_data = {'status': 'unknown',
                       'summary': {},
                       'details': {}}
        try:
            result_data['details'] = TimedCommand.get_command_output(['license_check.py', cache_path],
                                                                     graceful=False,
                                                                     is_json=True)
            result_data['status'] = result_data['details'].pop('status')
            result_data['summary'] = result_data['details'].pop('summary')
        except:
            self.log.exception("License scan failed")
            result_data['status'] = 'error'

        return result_data
