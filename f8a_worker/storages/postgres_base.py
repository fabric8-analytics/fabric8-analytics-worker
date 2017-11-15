#!/usr/bin/env python3

import os
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from selinon import DataStorage
from f8a_worker.models import Ecosystem


Base = declarative_base()


class PostgresBase(DataStorage):
    """Base class for PostgreSQL related adapters."""

    # Make these class variables and let derived classes share session so we
    # have only one postgres connection
    session = None
    connection_string = None
    encoding = None
    echo = None
    # Which table should be used for querying in derived classes
    query_table = None
    session_usage = 0

    _CONF_ERROR_MESSAGE = "PostgreSQL configuration mismatch, cannot use same database adapter " \
                          "base for connecting to different PostgreSQL instances"

    def __init__(self, connection_string, encoding='utf-8', echo=False):
        super().__init__()

        self.session_usage += 1
        connection_string = connection_string.format(**os.environ)
        if PostgresBase.connection_string is None:
            PostgresBase.connection_string = connection_string
        elif PostgresBase.connection_string != connection_string:
            raise ValueError("%s: %s != %s" % (self._CONF_ERROR_MESSAGE,
                                               PostgresBase.connection_string, connection_string))

        if PostgresBase.encoding is None:
            PostgresBase.encoding = encoding
        elif PostgresBase.encoding != encoding:
            raise ValueError(self._CONF_ERROR_MESSAGE)

        if PostgresBase.echo is None:
            PostgresBase.echo = echo
        elif PostgresBase.echo != echo:
            raise ValueError(self._CONF_ERROR_MESSAGE)

        # Assign what S3 storage should be used in derived classes
        self._s3 = None

    @property
    def s3(self):
        raise NotImplementedError()

    def is_connected(self):
        return PostgresBase.session is not None

    def connect(self):
        # Keep one connection alive and keep overflow unlimited so we can add
        # more connections in our jobs service
        engine = create_engine(
            self.connection_string,
            encoding=self.encoding,
            echo=self.echo,
            isolation_level="AUTOCOMMIT",
            pool_size=1,
            max_overflow=-1
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

        try:
            record = PostgresBase.session.query(self.query_table).\
                                          filter_by(worker_id=task_id).\
                                          one()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        assert record.worker == task_name

        return self._retrieve_task_result(record)

    def _retrieve_task_result(self, record):
        raise NotImplementedError()

    def _create_result_entry(self, node_args, flow_name, task_name, task_id, error=False):
        raise NotImplementedError()

    def store(self, node_args, flow_name, task_name, task_id, result):
        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(
            node_args,
            flow_name,
            task_name,
            task_id,
            error=result.get('status') == 'error'
        )
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        res.s3_version_id = self.s3.store_task_result(node_args, task_name, result)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        return res.s3_version_id

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info):
        #
        # We do not store errors in init tasks - the reasoning is that init
        # tasks are responsible for creating database entries. We cannot rely
        # that all database entries are successfully created. By doing this we
        # remove weird-looking errors like (un-committed changes due to errors
        # in init task):
        #   DETAIL: Key (package_analysis_id)=(1113452) is not present in table "package_analyses".
        #
        # Note that raising NotImplementedError will cause Selinon to treat
        # behaviour correctly - no error is permanently stored (but reported in
        # logs).
        #
        if task_name in ('InitPackageFlow', 'InitAnalysisFlow'):
            raise NotImplementedError()

        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(node_args, flow_name, task_name, task_id, error=True)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    def get_ecosystem(self, name):
        if not self.is_connected():
            self.connect()

        return Ecosystem.by_name(PostgresBase.session, name)

    def __del__(self):
        print("Destructor is called for %s" % self.__class__.__name__)
        self.session_usage -= 1
        if self.session_usage == 0 and self.is_connected():
            print("Disconnecting in %s" % self.__class__.__name__)
            self.disconnect()
        print("Destructor finished for %s" % self.__class__.__name__)
