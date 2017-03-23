from cucoslib.base import BaseTask


class GraphSyncTask(BaseTask):
    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        raise NotImplementedError()
