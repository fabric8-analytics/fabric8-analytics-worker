from cucoslib.base import BaseTask
from cucoslib.utils import get_analysis_by_id


class ResultCollector(BaseTask):
    """
    Collect all results and return them as a dict
    """
    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))
        self._strict_assert(arguments.get('document_id'))

        result = get_analysis_by_id(arguments['ecosystem'],
                                    arguments['name'],
                                    arguments['version'],
                                    arguments['document_id']).to_dict()
        return result
