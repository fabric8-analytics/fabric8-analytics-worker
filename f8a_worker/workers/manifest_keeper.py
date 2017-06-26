import os
from selinon import StoragePool
from f8a_worker.base import BaseTask


class ManifestKeeperTask(BaseTask):
    description = 'Keep manifest stored on S3'
    # we don't want to add `_audit` etc into the manifest submitted
    add_audit_info = False

    def execute(self, arguments):
        self._strict_assert(arguments.get('manifest'))
        self._strict_assert(arguments.get('external_request_id'))

        # TODO: retrieve from postgres
        return arguments['manifest']
