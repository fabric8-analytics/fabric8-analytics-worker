"""Import to graph task."""

from f8a_worker.base import BaseTask
import requests
from os import environ
from selinon import StoragePool
from f8a_worker.models import Ecosystem


class GraphImporterTask(BaseTask):
    """Import to graph task."""

    _SERVICE_HOST = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_HOST", "bayesian-data-importer")
    _SERVICE_PORT = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_PORT", "9192")
    _INGEST_SERVICE_ENDPOINT = "api/v1/ingest_to_graph"
    _SELECTIVE_SERVICE_ENDPOINT = "api/v1/selective_ingest"
    _INGEST_API_URL = "http://{host}:{port}/{endpoint}".format(host=_SERVICE_HOST,
                                                               port=_SERVICE_PORT,
                                                               endpoint=_INGEST_SERVICE_ENDPOINT)

    _SELECTIVE_API_URL = "http://{host}:{port}/{endpoint}".format(
        host=_SERVICE_HOST,
        port=_SERVICE_PORT,
        endpoint=_SELECTIVE_SERVICE_ENDPOINT)

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        if not arguments.get('force_graph_sync'):
            self._strict_assert(arguments.get('document_id'))

        rdb = StoragePool.get_connected_storage('BayesianPostgres')
        ecosystem_backend = Ecosystem.by_name(rdb.session, arguments.get('ecosystem')).backend.name
        package_list = [
            {
                        'ecosystem': ecosystem_backend,
                        'name': arguments['name'],
                        'version': arguments.get('version'),
                        'source_repo': arguments.get('ecosystem')
            }
        ]

        # If we force graph sync, sync all task results, otherwise only
        # finished in this analysis run
        if not arguments.get('force_graph_sync'):
            # Tasks that need sync to graph start lowercase.
            param = {
                'select_ingest': [task_name
                                  for task_name in self.storage.get_finished_task_names(
                                      arguments['document_id'])
                                  if task_name[0].islower()],
                'package_list': package_list
            }
            endpoint = self._SELECTIVE_API_URL
        else:
            param = package_list
            endpoint = self._INGEST_API_URL

        self.log.info("Invoke graph importer at url: '%s' for %s", endpoint, param)
        response = requests.post(endpoint, json=param)

        if response.status_code != 200:
            raise RuntimeError("Failed to invoke graph import at '%s' for %s" % (endpoint, param))

        self.log.info("Graph import succeeded with response: %s", response.text)
