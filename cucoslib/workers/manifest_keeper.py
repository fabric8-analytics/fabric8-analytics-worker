import os
from selinon import StoragePool
from cucoslib.base import BaseTask


class ManifestKeeperTask(BaseTask):
    description = 'Keep manifest stored on S3'

    def execute(self, arguments):
        self._strict_assert(arguments.get('manifest'))
        self._strict_assert(arguments.get('external_request_id'))

        # TODO: retrieve from postgres
        return arguments['manifest']
