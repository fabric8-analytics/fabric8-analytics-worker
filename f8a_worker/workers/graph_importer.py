from f8a_worker.base import BaseTask
from f8a_worker.workers.graph_importer_utils import import_epv_from_s3_http
import requests
from os import environ


class GraphImporterTask(BaseTask):

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('document_id'))

        package_list = [
            {
                'ecosystem': arguments['ecosystem'],
                'name': arguments['name'],
                'version': arguments.get('version')
            }
        ]
        select_ingest = [task_name
                         for task_name in self.storage.get_finished_task_names(arguments['document_id'])
                         if task_name[0].islower()]

        report = import_epv_from_s3_http(list_epv=package_list, select_doc=select_ingest)
        response = {'message': report.get('message'),
                    'epv': package_list,
                    'count_imported_EPVs': report.get('count_imported_EPVs')}

        self.log.info(response)
