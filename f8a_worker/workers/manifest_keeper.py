"""Class to keep manifest stored on S3."""

from selinon import StoragePool
from f8a_worker.base import BaseTask
from f8a_worker.models import StackAnalysisRequest
from sqlalchemy.exc import SQLAlchemyError


class ManifestKeeperTask(BaseTask):
    """Keep manifest stored on S3."""

    # we don't want to add `_audit` etc into the manifest submitted
    add_audit_info = False

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('external_request_id'))

        postgres = StoragePool.get_connected_storage('BayesianPostgres')

        try:
            results = postgres.session.query(StackAnalysisRequest)\
                        .filter(StackAnalysisRequest.id == arguments.get('external_request_id'))\
                        .first()
        except SQLAlchemyError:
            postgres.session.rollback()
            raise

        manifests = []
        if results is not None:
            row = results.to_dict()
            request_json = row.get("requestJson", {})
            manifests = request_json.get('manifest', [])

        return {'manifest': manifests}
