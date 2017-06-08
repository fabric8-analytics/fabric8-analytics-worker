#!/usr/bin/env python3

from sqlalchemy.ext.declarative import declarative_base
from selinon import StoragePool
from cucoslib.models import Analysis, Ecosystem, Package, Version, WorkerResult
from cucoslib.utils import MavenCoordinates
from sqlalchemy.orm.exc import NoResultFound

from .postgres_base import PostgresBase


Base = declarative_base()


class BayesianPostgres(PostgresBase):
    """Adapter used for EPV analyses."""

    query_table = WorkerResult

    @property
    def s3(self):
        # Do S3 retrieval lazily so tests do not complain about S3 setup
        if self._s3 is None:
            self._s3 = StoragePool.get_connected_storage('S3Data')
        return self._s3

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, result, error=False):
        return WorkerResult(
            worker=task_name,
            worker_id=task_id,
            analysis_id=node_args.get('document_id') if isinstance(node_args, dict) else None,
            task_result=result,
            error=error or result.get('status') == 'error' if isinstance(result, dict) else None,
            external_request_id=node_args.get('external_request_id') if isinstance(node_args, dict) else None
        )

    def get_latest_task_result(self, ecosystem, package, version, task_name, error=False):
        """Get latest task result based on task name
        
        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param version: package version
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        """
        # TODO: we should store date timestamps directly in WorkerResult
        if not self.is_connected():
            self.connect()

        try:
            record = PostgresBase.session.query(WorkerResult).join(Analysis).join(Version).join(Package).join(Ecosystem).\
                filter(WorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Version.identifier == version).\
                filter(Ecosystem.name == ecosystem).\
                filter(WorkerResult.error.is_(error)).\
                order_by(Analysis.finished_at.desc()).first()
        except NoResultFound:
            return None

        return record

    def get_analysis_count(self, ecosystem, package, version):
        """Get count of previously scheduled analysis for given EPV triplet.

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        :param version: str, Package version
        :return: analysis count
        """
        if ecosystem == 'maven':
            package = MavenCoordinates.normalize_str(package)

        count = PostgresBase.session.query(Analysis).\
            join(Version).join(Package).join(Ecosystem).\
            filter(Ecosystem.name == ecosystem).\
            filter(Package.name == package).\
            filter(Version.identifier == version).\
            count()

        return count

    def get_worker_id_count(self, worker_id):
        """Get number of results that has the given worker_id assigned (should be always 0 or 1).

        :param worker_id: unique worker id
        :return: worker result count
        """
        return PostgresBase.session.query(WorkerResult).filter(WorkerResult.worker_id == worker_id).count()

    def get_analysis_by_id(self, analysis_id):
        """Get result of previously scheduled analysis

        :param analysis_id: str, ID of analysis
        :return: analysis result
        """

        found = PostgresBase.session.query(Analysis).\
            filter(Analysis.id == analysis_id).\
            one()

        return found
