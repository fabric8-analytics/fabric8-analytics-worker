from selinon import StoragePool
from sqlalchemy.exc import SQLAlchemyError
from f8a_worker.base import BaseTask


class _ResultCollectorBase(BaseTask):
    """Collect results, upload them to S3 and store reference to results in WorkerResult.

    This class collects all results that were computed, upload them to S3 and store version
    reference to results in WorkerResult
    """

    def do_run(self, arguments, s3, postgres, results):
        for worker_result in results.raw_analyses:
            # We don't want to store tasks that do book-keeping for Selinon's
            # Dispatcher (starting uppercase)
            if worker_result.worker[0].isupper():
                continue

            if not postgres.is_real_task_result(worker_result.task_result):
                # Do not overwrite results stored on S3 with references to
                # their version - this can occur on selective task runs.
                continue

            version_id = s3.store_task_result(arguments, worker_result.worker,
                                              worker_result.task_result)
            # Substitute task's result with version that we got on S3
            worker_result.task_result = {'version_id': version_id}

        if hasattr(results, 'version'):  # update only for version Analysis objects
            results.version.synced2graph = False

        try:
            postgres.session.commit()
        except SQLAlchemyError:
            postgres.session.rollback()
            raise

        s3.store_base_file_record(arguments, results.to_dict())


class ResultCollector(_ResultCollectorBase):
    def run(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))
        self._strict_assert(arguments.get('document_id'))

        postgres = StoragePool.get_connected_storage('BayesianPostgres')
        results = postgres.get_analysis_by_id(arguments['document_id'])

        return self.do_run(arguments,
                           StoragePool.get_connected_storage('S3Data'),
                           postgres,
                           results)


class PackageResultCollector(_ResultCollectorBase):
    def run(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('document_id'))

        postgres = StoragePool.get_connected_storage('PackagePostgres')
        results = postgres.get_analysis_by_id(arguments['document_id'])

        return self.do_run(arguments,
                           StoragePool.get_connected_storage('S3PackageData'),
                           postgres,
                           results)
