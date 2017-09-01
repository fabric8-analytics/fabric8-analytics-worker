import os
from selinon import StoragePool
from f8a_worker.base import BaseTask
from f8a_worker.models import StackAnalysisRequest


class ManifestKeeperTask(BaseTask):
    description = 'Keep manifest stored on S3'
    # we don't want to add `_audit` etc into the manifest submitted
    add_audit_info = False

    def execute(self, arguments):
        self._strict_assert(arguments.get('external_request_id'))

        postgres = StoragePool.get_connected_storage('BayesianPostgres')
        results = postgres.session.query(StackAnalysisRequest)\
                        .filter(StackAnalysisRequest.id == arguments.get('external_request_id'))

        manifests = []
        if results.count() > 0:
            row = results.first().to_dict()
            request_json = row.get("requestJson", {})
            manifests = request_json.get('manifest', [])

        return {'manifest': manifests}
