from selinon import StoragePool
from cucoslib.base import BaseTask
from cucoslib.utils import get_analysis_by_id


class ResultCollector(BaseTask):
    """
    Collect all results that were computed, upload them to S3 and store version reference to results in WorkerResult
    """
    def run(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))
        self._strict_assert(arguments.get('document_id'))

        s3 = StoragePool.get_connected_storage('S3Data')
        postgres = StoragePool.get_connected_storage('BayesianPostgres')

        results = get_analysis_by_id(arguments['ecosystem'],
                                     arguments['name'],
                                     arguments['version'],
                                     arguments['document_id'])

        for worker_result in results.raw_analyses:
            # We don't want to store tasks that do book-keeping for Selinon's Dispatcher (starting uppercase)
            if worker_result.worker[0].isupper():
                continue

            version_id = s3.store_task_result(arguments, worker_result.worker, worker_result.task_result)
            # Substitute task's result with version that we got on S3
            worker_result.task_result = {'version_id': version_id}

        postgres.session.commit()
        s3.store_base_file_record(arguments, results.to_dict())
