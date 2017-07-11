import os
from selinon import StoragePool
from f8a_worker.base import BaseTask


class BookkeeperTask(BaseTask):
    description = 'Keep bookkeeping data on RDS'
    # we don't want to add `_audit` etc into the manifest submitted
    add_audit_info = False

    def execute(self, arguments):
        self._strict_assert(arguments.get('external_request_id'))
        self._strict_assert(arguments.get('data'))

        self.log.info("Request id = %s" % arguments.get('external_request_id'))

        postgres = StoragePool.get_connected_storage('BayesianPostgres')
        postgres.store_api_requests(arguments.get('external_request_id'), arguments.get('data'))
