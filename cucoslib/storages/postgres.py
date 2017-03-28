#!/usr/bin/env python3

import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from selinon import DataStorage, StoragePool
from cucoslib.models import Ecosystem, WorkerResult, Analysis
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
        if 'version_id' in task_result.keys() \
                and len(task_result.keys()) == 1:
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

        # TODO: I'm not sure whether request_id corresponds to
        # external_request_id, but external_request_id is not present
        res = WorkerResult(worker=task_name,
                           worker_id=task_id,
                           analysis_id=node_args.get('document_id'),
                           task_result=result,
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
        try:
            record = self.session.query(WorkerResult).join(Analysis).\
                filter(WorkerResult.worker == task_name).\
                order_by(Analysis.finished_at.desc()).first()
        except NoResultFound:
            return None

        return record
