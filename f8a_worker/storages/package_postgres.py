#!/usr/bin/env python3

from itertools import chain
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from selinon import StoragePool
from f8a_worker.models import PackageAnalysis, Ecosystem, Package, PackageWorkerResult
from f8a_worker.utils import MavenCoordinates

from .postgres_base import PostgresBase


Base = declarative_base()


class PackagePostgres(PostgresBase):
    """Adapter used for Package-level."""

    query_table = PackageWorkerResult

    @property
    def s3(self):
        # Do S3 retrieval lazily so tests do not complain about S3 setup
        if self._s3 is None:
            self._s3 = StoragePool.get_connected_storage('S3PackageData')
        return self._s3

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, error=False):
        return PackageWorkerResult(
            worker=task_name,
            worker_id=task_id,
            package_analysis_id=(node_args.get('document_id')
                                 if isinstance(node_args, dict) else None),
            error=error,
            external_request_id=(node_args.get('external_request_id')
                                 if isinstance(node_args, dict) else None)
        )

    def get_analysis_by_id(self, analysis_id):
        """Get result of previously scheduled analysis

        :param analysis_id: str, ID of analysis
        :return: analysis result
        """

        try:
            return PostgresBase.session.query(PackageAnalysis).\
                                        filter(PackageAnalysis.id == analysis_id).\
                                        one()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    def get_analysis_count(self, ecosystem, package):
        """Get count of previously scheduled analyses for given ecosystem-package.

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        :return: analysis count
        """
        if ecosystem == 'maven':
            package = MavenCoordinates.normalize_str(package)

        try:
            count = PostgresBase.session.query(PackageAnalysis).\
                                         join(Package).join(Ecosystem).\
                                         filter(Ecosystem.name == ecosystem).\
                                         filter(Package.name == package).\
                                         count()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return count

    def get_worker_id_count(self, worker_id):
        """Get number of results that has the given worker_id assigned (should be always 0 or 1).

        :param worker_id: unique worker id
        :return: worker result count
        """
        try:
            return PostgresBase.session.query(PackageWorkerResult).\
                filter(PackageWorkerResult.worker_id == worker_id).count()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    @staticmethod
    def get_finished_task_names(analysis_id):
        """Get name of tasks that finished in Analysis.

        :param analysis_id: analysis id for which task names should retrieved
        :return: a list of task names
        """
        try:
            task_names = PostgresBase.session.query(PackageWorkerResult.worker).\
                                              join(PackageAnalysis).\
                                              filter(PackageAnalysis.id == analysis_id).\
                                              filter(PackageWorkerResult.error.is_(False)).\
                                              all()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return list(chain(*task_names))

    def get_latest_task_result(self, ecosystem, package, task_name, error=False):
        """Get latest task result based on task name

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        """
        # TODO: we should store t date timestamps directly in PackageWorkerResult
        if not self.is_connected():
            self.connect()

        try:
            entry = PostgresBase.session.query(PackageWorkerResult).\
                join(PackageAnalysis).join(Package).join(Ecosystem).\
                filter(PackageWorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Ecosystem.name == ecosystem).\
                filter(PackageWorkerResult.error.is_(error)).\
                filter(PackageWorkerResult.s3_version_id.isnot(None)).\
                order_by(PackageAnalysis.finished_at.desc()).first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        if not entry:
            return None

        return self.s3.retrieve_task_result(ecosystem, package, task_name)

    def get_task_result_by_analysis_id(self, ecosystem, package, task_name, analysis_id):
        """Get latest task result based analysis id.

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param task_name: name of task for which the latest result should be obtained
        :param analysis_id: analysis id to be used
        """
        # TODO: we should store date timestamps directly in PackageWorkerResult
        if not self.is_connected():
            self.connect()

        try:
            entry = PostgresBase.session.query(PackageWorkerResult).\
                join(PackageAnalysis).\
                join(Package).join(Ecosystem).\
                filter(PackageWorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Ecosystem.name == ecosystem).\
                filter(PackageWorkerResult.error.is_(False)).\
                filter(PackageAnalysis.id == analysis_id).first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        if not entry:
            return None

        return self.s3.retrieve_task_result(
            ecosystem,
            package,
            task_name,
            version_id=entry.s3_version_id
        )

    def _retrieve_task_result(self, record):
        return self.s3.retrieve_task_result(
            record.ecosystem.name,
            record.package.name,
            record.worker,
            record.s3_version_id
        )

    def get_latest_task_entry(self, ecosystem, package, task_name, error=False):
        """Get latest task result based on task name

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        rather return Postgres entry
        """
        # TODO: we should store date timestamps directly in PackageWorkerResult
        if not self.is_connected():
            self.connect()

        try:
            entry = PostgresBase.session.query(PackageWorkerResult).\
                join(PackageAnalysis).\
                join(Package).join(Ecosystem).\
                filter(PackageWorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Ecosystem.name == ecosystem).\
                filter(PackageWorkerResult.error.is_(error)).\
                order_by(PackageAnalysis.finished_at.desc()).first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return entry
