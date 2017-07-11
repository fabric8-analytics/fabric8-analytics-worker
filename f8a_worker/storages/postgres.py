#!/usr/bin/env python3
import datetime
import hashlib
import json

from sqlalchemy import Date, cast
from sqlalchemy.ext.declarative import declarative_base
from selinon import StoragePool
from f8a_worker.models import Analysis, Ecosystem, Package, Version, WorkerResult, APIRequests
from f8a_worker.utils import MavenCoordinates
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
        """Get result of previously scheduled analysis5

        :param analysis_id: str, ID of analysis
        :return: analysis result
        """

        found = PostgresBase.session.query(Analysis).\
            filter(Analysis.id == analysis_id).\
            one()

        return found

    def check_api_user_entry(self, email):
        """Check if a user entry has already been made in api_requests

        :param email: str, user's email id
        :return: count of user's entry in api_requests
        """
        return PostgresBase.session.query(APIRequests).\
            filter(APIRequests.user_email == email).first()

    def store_in_bucket(self, content):
        s3 = StoragePool.get_connected_storage('S3UserProfileStore')
        s3.store_in_bucket(content)

    def store_api_requests(self, external_request_id, data):
        """Get result of previously scheduled analysis5

        :param external_request_id: str, ID of analysis
        :param data: bookkeeping data
        :return: None
        """
        if not self.is_connected():
            self.connect()

        profile_digest = None
        # Add user_profile to S3 if there is no api_requests entry available for today
        req = self.check_api_user_entry(data.get('user_email', None))
        if req:
            profile = json.dumps(data.get('user_profile'))
            profile_digest = hashlib.sha256(profile.encode('utf-8')).hexdigest()
            if profile_digest != req.user_profile_digest:
                self.store_in_bucket(profile)
        
        dt = datetime.datetime.now()
        req = APIRequests(
            id = external_request_id,
            api_name = data.get('api_name', None),
            submit_time = str(dt),
            user_email = data.get('user_email', None),
            user_profile_digest = profile_digest,
            origin = data.get('origin', None),
            request = data.get('request', None),
            team = data.get('team', None),
            recommendation = data.get('recommendation', None)
        )

        PostgresBase.session.add(req)
        PostgresBase.session.commit()
        return True
