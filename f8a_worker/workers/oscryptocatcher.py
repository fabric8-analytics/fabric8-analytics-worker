"""
Matches crypto algorithms in sources based on content

Output: list of files along with crypto algorithm they contain
"""

from f8a_worker.utils import TimedCommand
from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef
from f8a_worker.object_cache import ObjectCache


class OSCryptoCatcherTask(BaseTask):
    """ Runs oscryptocatcher tool for matching crypto algorithms """
    _analysis_name = 'crypto_algorithms'
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
        except Exception:
            results['status'] = 'error'

        return results
