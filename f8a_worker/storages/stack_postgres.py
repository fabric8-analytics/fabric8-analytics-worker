#!/usr/bin/env python3

from .postgres_base import PostgresBase

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from f8a_worker.models import WorkerResult


class StackPostgres(PostgresBase):
    def retrieve(self, flow_name, task_name, task_id):
        if not self.is_connected():
            self.connect()

        try:
            record = PostgresBase.session.query(WorkerResult). \
                filter_by(worker_id=task_id). \
                one()
        except (NoResultFound, MultipleResultsFound):
            raise
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise

        assert record.worker == task_name
        return record.task_result

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info):
        raise NotImplementedError()

    def store(self, node_args, flow_name, task_name, task_id, result):
        # Sanity checks
        if not self.is_connected():
            self.connect()

        res = WorkerResult(
            worker=task_name,
            worker_id=task_id,
            analysis_id=node_args.get('document_id') if isinstance(node_args, dict) else None,
            task_result=result,
            error=result.get('status') == 'error',
            external_request_id=(node_args.get('external_request_id')
                                 if isinstance(node_args, dict) else None)
        )

        try:
            PostgresBase.session.add(res)
            PostgresBase.session.commit()
        except SQLAlchemyError:
            PostgresBase.session.rollback()
            raise
