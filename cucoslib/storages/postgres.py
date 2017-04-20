#!/usr/bin/env python3

import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from selinon import DataStorage, StoragePool
from cucoslib.models import Analysis, Ecosystem, Package, Version, WorkerResult
from cucoslib.utils import MavenCoordinates
from sqlalchemy.orm.exc import NoResultFound


Base = declarative_base()


class BayesianPostgres(DataStorage):
    def __init__(self, connection_string, encoding='utf-8', echo=False):
        super().__init__()

        self.connection_string = connection_string
        self.encoding = encoding
        self.echo = echo
        self.session = None

    def is_connected(self):
        return self.session is not None

    def connect(self):
        engine = create_engine(self.connection_string.format(**os.environ),
                               encoding=self.encoding,
                               echo=self.echo,
                               poolclass=NullPool,
                               isolation_level="AUTOCOMMIT")
        self.session = sessionmaker(bind=engine)()
        Base.metadata.create_all(engine)

    def disconnect(self):
        if self.is_connected():
            self.session.close()
            self.session = None

    def retrieve(self, flow_name, task_name, task_id):
        if not self.is_connected():
            self.connect()

        record = self.session.query(WorkerResult).filter_by(worker_id=task_id).one()
        assert record.worker == task_name

        task_result = record.task_result
        if not self.is_real_task_result(task_result):
            # we synced results to S3, retrieve them from there
            # We do not care about some specific version, so no time-based collisions possible
            s3 = StoragePool.get_connected_storage('S3Data')
            return s3.retrieve_task_result(
                record.ecosystem.name,
                record.package.name,
                record.version.identifier,
                task_name
            )

        return task_result

    def store(self, node_args, flow_name, task_name, task_id, result):
        if not self.is_connected():
            self.connect()

        res = WorkerResult(worker=task_name,
                           worker_id=task_id,
                           analysis_id=node_args.get('document_id'),
                           task_result=result,
                           error=result.get('status') == 'error',
                           external_request_id=node_args.get('external_request_id'))
        try:
            self.session.add(res)
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info):
        if not self.is_connected():
            self.connect()

        res = WorkerResult(worker=task_name,
                           worker_id=task_id,
                           analysis_id=node_args.get('document_id'),
                           task_result=None,
                           error=True,
                           external_request_id=node_args.get('external_request_id'))
        try:
            self.session.add(res)
            self.session.commit()
        except:
            self.session.rollback()
            raise

    def get_ecosystem(self, name):
        if not self.is_connected():
            self.connect()

        return Ecosystem.by_name(self.session, name)

    def get_latest_task_result(self, ecosystem, package, version, task_name):
        """ Get latest task id based on task name """
        # TODO: we should store date timestamps directly in WorkerResult
        if not self.is_connected():
            self.connect()

        try:
            record = self.session.query(WorkerResult).join(Analysis).join(Ecosystem).join(Package).join(Version).\
                filter(WorkerResult.worker == task_name).\
                filter(Package.name == package).\
                filter(Version.identifier == version).\
                filter(Ecosystem.name == ecosystem).\
                order_by(Analysis.finished_at.desc()).first()
        except NoResultFound:
            return None

        return record

    @staticmethod
    def is_real_task_result(task_result):
        """ Check that the task result is not just S3 object version reference """
        return task_result and (len(task_result.keys()) != 1 or 'version_id' not in task_result.keys())

    def get_analysis_count(self, ecosystem, package, version):
        """Get count of previously scheduled analysis for given EPV triplet

        :param ecosystem: str, Ecosystem name
        :param package: str, Package name
        :param version: str, Package version
        :return: analysis count
        """
        if ecosystem == 'maven':
            package = MavenCoordinates.normalize_str(package)

        count = self.session.query(Analysis).\
            join(Version).join(Package).join(Ecosystem).\
            filter(Ecosystem.name == ecosystem).\
            filter(Package.name == package).\
            filter(Version.identifier == version).\
            count()

        return count

    def get_worker_id_count(self, worker_id):
        """ Get number of results that has the given worker_id assigned (should be always 0 or 1)

        :param worker_id: unique worker id
        :return: worker result count
        """
        return self.session.query(WorkerResult).filter(WorkerResult.worker_id == worker_id).count()
