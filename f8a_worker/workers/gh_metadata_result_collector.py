import requests
from selinon import StoragePool
from sqlalchemy.exc import SQLAlchemyError
import urllib.parse

from f8a_worker.base import BaseTask


class GitHubManifestMetadataResultCollector(BaseTask):
    """
    Collect all results that were computed, upload them to S3 and store version reference to results in WorkerResult
    """

    GITHUB_CONTENT_URL = 'http://raw.githubusercontent.com/'

    def run(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('repo_name'))
        self._strict_assert(arguments.get('document_id'))

        s3 = StoragePool.get_connected_storage('S3GitHubManifestMetadata')
        postgres = StoragePool.get_connected_storage('BayesianPostgres')

        results = postgres.get_analysis_by_id(arguments['document_id'])
        for worker_result in results.raw_analyses:

            # Skip auxiliary tasks (e.g. InitGitHubManifestMetadata)
            if worker_result.worker[0].isupper():
                continue

            # Retrieve raw manifest file and store it in S3
            if worker_result.worker == 'metadata':
                task_result = worker_result.task_result
                for detail in task_result.get('details', []):
                    if detail.get('path', None):
                        manifest_url = urllib.parse.urljoin(self.GITHUB_CONTENT_URL,
                                                            arguments['repo_name'] + '/' + detail['path'])
                        manifest_name = detail['path'].split('/', 1)[1]
                        response = requests.get(manifest_url)
                        if response.status_code == 200:
                            s3.store_raw_manifest(arguments['ecosystem'],
                                                  arguments['repo_name'],
                                                  manifest_name,
                                                  response.content)
                        else:
                            self.log.error('Unable to retrieve manifest file from %s', manifest_url)
                            continue

            result_name = worker_result.worker
            if result_name.startswith('gh_most_starred_'):
                result_name = result_name[len('gh_most_starred_'):]
            version_id = s3.store(arguments, self.flow_name, self.task_name, self.task_id,
                                  (result_name, worker_result.task_result))
            worker_result.task_result = {'version_id': version_id}
        try:
            postgres.session.commit()
        except SQLAlchemyError:
            postgres.session.rollback()
            raise
