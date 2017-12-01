from f8a_worker.base import BaseTask
from selinon import StoragePool
from selinon import FatalTaskError


class GraphImporterTask(BaseTask):
    """Sync data from S3 to graph database."""

    add_audit_info = False

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('document_id'))

        if self.task_name not in ('PackageGraphImporterTask', 'GraphImporterTask'):
            raise FatalTaskError("Unknown task name - cannot distinguish package vs. version level data")

        version_level = self.task_name == 'GraphImporterTask'

        postgres = StoragePool.get_connected_storage('BayesianPostgres' if version_level else 'PackagePostgres')
        s3 = StoragePool.get_connected_storage('S3Data' if version_level else 'S3PackageData')
        gremlin = StoragePool.get_connected_storage('GremlinHttp' if version_level else 'PackageGremlinHttp')

        adapter_kwargs = {
            'ecosystem': arguments['ecosystem'],
            'name': arguments['name']
        }
        if version_level:
            self._strict_assert(arguments.get('version'))
            adapter_kwargs['version'] = arguments['version']

        if arguments.get('force_graph_sync'):
            tasks_to_sync = s3.list_available_task_results(arguments)
            self.log.info("Force sync of all task results available on S3: %s", tasks_to_sync)
        else:
            tasks_to_sync = postgres.get_finished_task_names(arguments['document_id'])
            self.log.info("Syncing results of tasks in the current run: %s", tasks_to_sync)

        for task_name in tasks_to_sync:
            task_result = s3.retrieve_task_result(task_name=task_name, **adapter_kwargs)
            gremlin.store_task_result(task_name=task_name, task_result=task_result, **adapter_kwargs)
