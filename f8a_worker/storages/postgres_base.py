#!/usr/bin/env python3

"""Base class for PostgreSQL related adapters."""

import os

from selinon import DataStorage
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from f8a_worker.errors import TaskAlreadyExistsError
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

    _CONF_ERROR_MESSAGE = "PostgreSQL configuration mismatch, cannot use same database adapter " \
                          "base for connecting to different PostgreSQL instances"

    def __init__(self, connection_string, encoding='utf-8', echo=False):
        """Configure database connector."""
        super().__init__()

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

    def is_connected(self):
        """Check if the connection to database has been established."""
        return PostgresBase.session is not None

    def connect(self):
        """Establish connection to the databse."""
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
        """Close connection to the database."""
        if self.is_connected():
            PostgresBase.session.close()
            PostgresBase.session = None

    def retrieve(self, flow_name, task_name, task_id):
        """Retrieve the record identified by task_id from the database."""
        if not self.is_connected():
            self.connect()

        try:
            record = PostgresBase.session.query(self.query_table). \
                filter_by(worker_id=task_id). \
                one()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

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
        """Store the record identified by task_id into the database."""
        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(node_args, flow_name, task_name, task_id, result)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info, result=None):
        """Store error info to the Postgres database.

        Note: We do not store errors in init tasks.

        The reasoning is that init
        tasks are responsible for creating database entries. We cannot rely
        that all database entries are successfully created. By doing this we
        remove weird-looking errors like (un-committed changes due to errors
        in init task):
          DETAIL: Key (package_analysis_id)=(1113452) is not present in table "package_analyses".
        """
        if task_name in ('InitPackageFlow', 'InitAnalysisFlow')\
                or issubclass(exc_info[0], TaskAlreadyExistsError):
            return

        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = self._create_result_entry(node_args, flow_name, task_name, task_id, result=result,
                                        error=True)
        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except IntegrityError:
            # the result has been already stored before the error occurred
            # hence there is no reason to re-raise
            PostgresBase.session.rollback()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

    def get_ecosystem(self, name):
        """Get ecosystem by name."""
        if not self.is_connected():
            self.connect()

        return Ecosystem.by_name(PostgresBase.session, name)

    @staticmethod
    def is_real_task_result(task_result):
        """Check that the task result is not just S3 object version reference."""
        return task_result and (len(task_result.keys()) != 1 or
                                'version_id' not in task_result.keys())
