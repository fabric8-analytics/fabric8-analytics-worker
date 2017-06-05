from selinon import StoragePool
from cucoslib.base import BaseTask

import urllib.parse
import requests
import os


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

        results = postgres.get_analysis_by_id(arguments['document_id'], db_session=postgres.session)
        for worker_result in results.raw_analyses:

            # Skip auxiliary tasks (e.g. InitGitHubManifestMetadata)
            if worker_result.worker[0].isupper():
                continue

            # Retrieve raw manifest file and store it in S3
            if worker_result.worker == 'metadata':
                task_result = worker_result.task_result
                for index, detail in enumerate(task_result.get('details', [])):
                    if detail.get('path', None):
                        manifest_url = urllib.parse.urljoin(self.GITHUB_CONTENT_URL,
                                                            arguments['repo_name'] + '/' + detail['path'])
                        manifest_name = os.path.basename(detail['path'])
                        response = requests.get(manifest_url)
                        if response.status_code == 200:
                            s3.store_raw_manifest(arguments['ecosystem'],
                                                  arguments['repo_name'],
                                                  str(index) + '-' + manifest_name,
                                                  response.content)
                        else:
                            self.log.error('Unable to retrieve manifest file from %s', manifest_url)
                            continue

            version_id = s3.store(arguments, self.flow_name, self.task_name, self.task_id,
                                  (worker_result.worker, worker_result.task_result))
            worker_result.task_result = {'version_id': version_id}
        postgres.session.commit()
