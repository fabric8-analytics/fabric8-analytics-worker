#!/usr/bin/env python3

"""Adapter used for EPV analyses."""

import datetime
import json
from itertools import chain

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from selinon import StoragePool

from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Analysis, Ecosystem, Package, Version, WorkerResult, APIRequests
from f8a_worker.models import ComponentAnalysesRequests
from f8a_worker.utils import MavenCoordinates

from .postgres_base import PostgresBase
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class BayesianPostgres(PostgresBase):
    """Adapter used for EPV analyses."""

    query_table = WorkerResult

    @property
    def s3(self):
        """Retrieve the connector to the S3 database."""
        # Do S3 retrieval lazily so tests do not complain about S3 setup
        if self._s3 is None:
            self._s3 = StoragePool.get_connected_storage('S3Data')
        return self._s3

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, result, error=None):
        if error is None and isinstance(result, dict):
            error = result.get('status') == 'error'

        return WorkerResult(
            worker=task_name,
            worker_id=task_id,
            started_at=result.get('_audit', {}).get('started_at') if result else None,
            ended_at=result.get('_audit', {}).get('ended_at') if result else None,
            analysis_id=node_args.get('document_id') if isinstance(node_args, dict) else None,
            task_result=result,
            error=error,
            external_request_id=(node_args.get('external_request_id')
                                 if isinstance(node_args, dict) else None)
        )

    def get_latest_task_result(self, ecosystem, package, version, task_name):
        """Get latest task result based on task name.

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param version: package version
        :param task_name: name of task for which the latest result should be obtained
        rather return Postgres entry
        """
        # TODO: we should store date timestamps directly in WorkerResult
        if not self.is_connected():
            self.connect()

        try:
            entry = PostgresBase.session.query(WorkerResult.task_result).\
                join(Analysis).join(Version).join(Package).join(Ecosystem).\
                filter(WorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Version.identifier == version).\
                filter(Ecosystem.name == ecosystem).\
                filter(WorkerResult.error.is_(False)).\
                order_by(Analysis.finished_at.desc()).first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        if not entry:
            return None

        if not self.is_real_task_result(entry.task_result):
            return self.s3.retrieve_task_result(ecosystem, package, version, task_name)

        return entry.task_result

    def get_latest_task_entry(self, ecosystem, package, version, task_name, error=False):
        """Get latest task result based on task name.

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param version: package version
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        """
        # TODO: we should store date timestamps directly in PackageWorkerResult
        if not self.is_connected():
            self.connect()

        try:
            entry = PostgresBase.session.query(WorkerResult).\
                join(Analysis).\
                join(Package).join(Ecosystem).\
                filter(WorkerResult.worker == task_name).\
                filter(Version.identifier == version). \
                filter(Package.name == package).\
                filter(Ecosystem.name == ecosystem).\
                filter(WorkerResult.error.is_(error)).\
                order_by(Analysis.finished_at.desc()).first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return entry

    @staticmethod
    def get_analysis_count(ecosystem, package, version):
        """Get count of previously scheduled analysis for given EPV triplet.

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        :param version: str, Package version
        :return: analysis count
        """
        if Ecosystem.by_name(PostgresBase.session, ecosystem).is_backed_by(EcosystemBackend.maven):
            package = MavenCoordinates.normalize_str(package)

        try:
            count = PostgresBase.session.query(Analysis).\
                                         join(Version).join(Package).join(Ecosystem).\
                                         filter(Ecosystem.name == ecosystem).\
                                         filter(Package.name == package).\
                                         filter(Version.identifier == version).\
                                         count()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return count

    @staticmethod
    def get_finished_task_names(analysis_id):
        """Get name of tasks that finished in Analysis.

        :param analysis_id: analysis id for which task names should retrieved
        :return: a list of task names
        """
        try:
            task_names = PostgresBase.session.query(WorkerResult.worker).\
                                              join(Analysis).\
                                              filter(Analysis.id == analysis_id).\
                                              filter(WorkerResult.error.is_(False)).\
                                              all()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return list(chain(*task_names))

    @staticmethod
    def get_worker_id_count(worker_id):
        """Get number of results that has the given worker_id assigned (should be always 0 or 1).

        :param worker_id: unique worker id
        :return: worker result count
        """
        try:
            return PostgresBase.session.query(WorkerResult).filter(
                WorkerResult.worker_id == worker_id).count()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    @staticmethod
    def get_analysis_by_id(analysis_id):
        """Get result of previously scheduled analysis.

        :param analysis_id: str, ID of analysis
        :return: analysis result
        """
        try:
            return PostgresBase.session.query(Analysis).\
                                        filter(Analysis.id == analysis_id).\
                                        one()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    @staticmethod
    def check_api_user_entry(email):
        """Check if a user entry has already been made in api_requests.

        :param email: str, user's email id
        :return: First entry in api_requests table with matching email id
        """
        try:
            return PostgresBase.session.query(APIRequests).\
                                        filter(APIRequests.user_email == email).\
                                        first()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    @staticmethod
    def store_in_bucket(content):
        """Store the conetent into S3 bucket."""
        # TODO: move to appropriate S3 storage
        s3 = StoragePool.get_connected_storage('S3UserProfileStore')
        s3.store_in_bucket(content)

    def store_api_requests_post(self, arguments):
        """Store result of previously scheduled component analysis.

        :param request_id: str, ID of analysis
        :return: True/False
        """
        if not self.is_connected():
            self.connect()

        dt = datetime.datetime.utcnow()

        req = ComponentAnalysesRequests(
            request_id=arguments.get('external_request_id'),
            user_id=arguments['data'].get('user_id'),
            submit_time=str(dt),
            ecosystem=arguments['data'].get('ecosystem'),
            user_agent=arguments['data'].get('user_agent'),
            stack_data=json.dumps(arguments['data'].get('packages_list')),
            manifest_hash=arguments['data'].get('manifest_hash')
        )

        try:
            PostgresBase.session.add(req)
            PostgresBase.session.commit()
        except IntegrityError:
            # This is OK, the same request has been processed twice
            PostgresBase.session.rollback()
            pass
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return True

    @staticmethod
    def get_analysed_versions(ecosystem, package):
        """Return all already analysed versions for the given package.

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        return: a list of package version identifiers of already analysed versions
        """
        try:
            return chain(*PostgresBase.session.query(Version.identifier).
                         join(Analysis).join(Package).join(Ecosystem).
                         filter(Ecosystem.name == ecosystem).
                         filter(Package.name == package).
                         filter(Analysis.finished_at.isnot(None)).
                         distinct().all())
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise
