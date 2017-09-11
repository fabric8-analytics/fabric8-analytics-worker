#!/usr/bin/env python3
import datetime
import hashlib
import json
from itertools import chain

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from selinon import StoragePool
from f8a_worker.models import Analysis, Ecosystem, Package, Version, WorkerResult, APIRequests
from f8a_worker.utils import MavenCoordinates

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

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, result, error=None):
        if error is None and isinstance(result, dict):
            error = result.get('status') == 'error'

        return WorkerResult(
            worker=task_name,
            worker_id=task_id,
            analysis_id=node_args.get('document_id') if isinstance(node_args, dict) else None,
            task_result=result,
            error=error,
            external_request_id=node_args.get('external_request_id') if isinstance(node_args, dict) else None
        )

    def get_latest_task_result(self, ecosystem, package, version, task_name):
        """Get latest task result based on task name
        
        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param version: package version
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        :param real: if False, do not check results that are stored on S3 but rather return Postgres entry
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
        """Get latest task result based on task name

        :param ecosystem: name of the ecosystem
        :param package: name of the package
        :param task_name: name of task for which the latest result should be obtained
        :param error: if False, avoid returning entries that track errors
        :param real: if False, do not check results that are stored on S3 but rather return Postgres entry
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

    def get_analysis_count(self, ecosystem, package, version):
        """Get count of previously scheduled analysis for given EPV triplet.

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        :param version: str, Package version
        :return: analysis count
        """
        if ecosystem == 'maven':
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

    def get_worker_id_count(self, worker_id):
        """Get number of results that has the given worker_id assigned (should be always 0 or 1).

        :param worker_id: unique worker id
        :return: worker result count
        """
        try:
            return PostgresBase.session.query(WorkerResult).filter(WorkerResult.worker_id == worker_id).count()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    @staticmethod
    def get_analysis_by_id(analysis_id):
        """Get result of previously scheduled analysis

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
        """Check if a user entry has already been made in api_requests

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
        # TODO: move to appropriate S3 storage
        s3 = StoragePool.get_connected_storage('S3UserProfileStore')
        s3.store_in_bucket(content)

    def store_api_requests(self, external_request_id, data, dep_data):
        """Get result of previously scheduled analysis5

        :param external_request_id: str, ID of analysis
        :param data: bookkeeping data
        :return: True/False
        """
        if not self.is_connected():
            self.connect()

        # Add user_profile to S3 if there is no api_requests entry available for today
        req = self.check_api_user_entry(data.get('user_email', None))

        profile = json.dumps(data.get('user_profile'))
        profile_digest = hashlib.sha256(profile.encode('utf-8')).hexdigest()
        request_digest = hashlib.sha256(json.dumps(dep_data).encode('utf-8')).hexdigest()

        dt = datetime.datetime.now()
        if req:
            if profile_digest != req.user_profile_digest:
                self.store_in_bucket(data.get('user_profile'))
        else:
            self.store_in_bucket(data.get('user_profile'))
                
        req = APIRequests(
            id=external_request_id,
            api_name=data.get('api_name', None),
            submit_time=str(dt),
            user_email=data.get('user_email', None),
            user_profile_digest=profile_digest,
            origin=data.get('origin', None),
            team=data.get('team', None),
            recommendation=data.get('recommendation', None),
            request_digest=request_digest
        )

        try:
            PostgresBase.session.add(req)
            PostgresBase.session.commit()
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
                         join(Analysis).join(Package).join(Ecosystem).\
                         filter(Ecosystem.name == ecosystem).\
                         filter(Package.name == package).\
                         filter(Analysis.finished_at.isnot(None)).\
                         distinct().all())
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise
