from selinon import StoragePool
from cucoslib.base import BaseTask


class GitHubManifestMetadataResultCollector(BaseTask):
    """
    Collect all results that were computed, upload them to S3 and store version reference to results in WorkerResult
    """

    def run(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('repo_name'))
        self._strict_assert(arguments.get('document_id'))

        s3 = StoragePool.get_connected_storage('S3GitHubManifestMetadata')
        postgres = StoragePool.get_connected_storage('BayesianPostgres')

        results = postgres.get_analysis_by_id(arguments['document_id'], db_session=postgres.session)
        for worker_result in results.raw_analyses:

            # Skip auxiliary tasks (e.g. InitGitHubManifestMetadata)
            if worker_result.worker[0].isupper():
                continue

            version_id = s3.store(arguments, self.flow_name, self.task_name, self.task_id,
                                  (worker_result.worker, worker_result.task_result))
            worker_result.task_result = {'version_id': version_id}
        postgres.session.commit()
