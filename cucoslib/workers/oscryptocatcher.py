"""
Matches crypto algorithms in sources based on content

Output: list of files along with crypto algorithm they contain
"""

from cucoslib.utils import TimedCommand
from cucoslib.base import BaseTask
from cucoslib.schemas import SchemaRef
from cucoslib.object_cache import ObjectCache


class OSCryptoCatcherTask(BaseTask):
    _analysis_name = 'crypto_algorithms'
    description = "Runs oscryptocatcher tool for matching crypto algorithms"
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        cache_path = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()

        results = {'status': 'unknown',
                   'summary': {},
                   'details': []}

        try:
            oscc = TimedCommand.get_command_output(['oscryptocatcher', '--subdir-in-result', cache_path],
                                                   graceful=False, is_json=True)

            self.log.debug("oscryptocatcher %s output: %s", cache_path, oscc)
            results['details'] = oscc['details']
            results['summary'] = oscc['summary']
            results['status'] = 'success'
        except:
            results['status'] = 'error'

        return results
