#!/usr/bin/env python3

import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from selinon import DataStorage
from cucoslib.models import Analysis, Ecosystem, Package, Version, WorkerResult


Base = declarative_base()


class PostgresBase(DataStorage):
    """Base class for PostgreSQL related adapters."""

    # Make these class variables and let derived classes share session so we have only one postgres connection
    session = None
    connection_string = None
    encoding = None
    echo = None
    # Which table should be used for querying in derived classes
    query_table = None

    _CONF_ERROR_MESSAGE = "PostgreSQL configuration mismatch, cannot use same database adapter base for connecting " \
                          "to different PostgreSQL instances"

    def __init__(self, connection_string, encoding='utf-8', echo=False):
        super().__init__()

        connection_string = connection_string.format(**os.environ)
        if PostgresBase.connection_string is None:
            PostgresBase.connection_string = connection_string
        elif PostgresBase.connection_string != connection_string:
            raise ValueError("%s: %s != %s" % (self._CONF_ERROR_MESSAGE, PostgresBase.connection_string, connection_string))

        if PostgresBase.encoding is None:
            PostgresBase.encoding = encoding
        elif PostgresBase.encoding != encoding:
            raise ValueError(self._CONF_ERROR_MESSAGE)

        if PostgresBase.echo is None:
            PostgresBase.echo = echo
        elif PostgresBase.echo != echo:
            raise ValueError(self._CONF_ERROR_MESSAGE)

        # TODO(Fridolin): make connection shared across all derived adapters to save number of connections
        # Assign what S3 storage should be used in derived classes
        self._s3 = None

    def is_connected(self):
        return PostgresBase.session is not None

    def connect(self):
        engine = create_engine(
            self.connection_string,
            encoding=self.encoding,
            echo=self.echo,
            poolclass=NullPool,
            isolation_level="AUTOCOMMIT"
        )
        PostgresBase.session = sessionmaker(bind=engine)()
        Base.metadata.create_all(engine)

    def disconnect(self):
        if self.is_connected():
            PostgresBase.session.close()
            PostgresBase.session = None

    def retrieve(self, flow_name, task_name, task_id):
        if not self.is_connected():
            self.connect()

        record = PostgresBase.session.query(self.query_table).filter_by(worker_id=task_id).one()
        assert record.worker == task_name

        task_result = record.task_result
        if not self.is_real_task_result(task_result):
            # we synced results to S3, retrieve them from there
            # We do not care about some specific version, so no time-based collisions possible
            return self.s3.retrieve_task_result(
                record.ecosystem.name,
                record.package.name,
                record.version.identifier,
                task_name
            )

        return task_result

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, result, error=False):
        raise NotImplementedError()

    def store(self, node_args, flow_name, task_name, task_id, result):
        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(node_args, flow_name, task_name, task_id, result)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except:
            PostgresBase.session.rollback()
            raise

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info):
        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(node_args, flow_name, task_name, task_id, result=None, error=True)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except:
            PostgresBase.session.rollback()
            raise

    def get_ecosystem(self, name):
        if not self.is_connected():
            self.connect()

        return Ecosystem.by_name(PostgresBase.session, name)

    @staticmethod
    def is_real_task_result(task_result):
        """Check that the task result is not just S3 object version reference."""
        return task_result and (len(task_result.keys()) != 1 or 'version_id' not in task_result.keys())
