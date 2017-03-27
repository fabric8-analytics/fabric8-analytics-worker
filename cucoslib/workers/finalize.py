"""
Clean up shared volume
"""

import datetime
from cucoslib.utils import json_serial
from cucoslib.base import BaseTask
from cucoslib.models import Analysis


class FinalizeTask(BaseTask):
    def run(self, arguments):
        self._strict_assert(arguments.get('document_id'))

        # As we are the last, mark finished_at
        if not self.storage.is_connected():
            self.storage.connect()

        try:
            record = self.storage.session.query(Analysis).filter(Analysis.id == arguments['document_id']).one()
            record.finished_at = json_serial(datetime.datetime.now())
            record.release = '{}:{}:{}'.format(arguments.get('ecosystem'),
                                               arguments.get('name'),
                                               arguments.get('version'))
            self.storage.session.commit()
        except:
            self.storage.session.rollback()
            raise

        # Commented out for now since we want to sync to S3
        #if self.task_name.endswith('Error'):
        #    raise RuntimeError("Flow %s failed" % self.flow_name)
