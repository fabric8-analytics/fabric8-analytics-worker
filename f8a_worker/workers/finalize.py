import datetime
from sqlalchemy.exc import SQLAlchemyError
from f8a_worker.utils import json_serial
from f8a_worker.base import BaseTask
from f8a_worker.models import Analysis, PackageAnalysis


class FinalizeTask(BaseTask):
    """Finish EPV analysis flow and store audit."""
    def run(self, arguments):
        self._strict_assert(arguments.get('document_id'))

        try:
            record = self.storage.session.query(Analysis).\
                filter(Analysis.id == arguments['document_id']).one()
            record.finished_at = json_serial(datetime.datetime.now())
            record.release = '{}:{}:{}'.format(arguments.get('ecosystem'),
                                               arguments.get('name'),
                                               arguments.get('version'))
            self.storage.session.commit()
        except SQLAlchemyError:
            self.storage.session.rollback()
            raise

        # Commented out for now since we want to sync to S3
        #if self.task_name.endswith('Error'):
        #    raise RuntimeError("Flow %s failed" % self.flow_name)


class PackageFinalizeTask(BaseTask):
    """Finish Package-level flow and store audit."""
    def run(self, arguments):
        self._strict_assert(arguments.get('document_id'))

        try:
            record = self.storage.session.query(PackageAnalysis).\
                filter(PackageAnalysis.id == arguments['document_id']).one()
            record.finished_at = json_serial(datetime.datetime.now())
            self.storage.session.commit()
        except SQLAlchemyError:
            self.storage.session.rollback()
            raise

        # Commented out for now since we want to sync to S3
        #if self.task_name.endswith('Error'):
        #    raise RuntimeError("Flow %s failed" % self.flow_name)
