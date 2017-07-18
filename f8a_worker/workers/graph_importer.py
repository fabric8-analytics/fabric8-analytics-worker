from f8a_worker.base import BaseTask
import requests
from os import environ


class GraphImporterTask(BaseTask):
    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        epv = {'ecosystem': arguments['ecosystem'], 'name': arguments['name']}
        if self.flow_name == 'bayesianPackageFlow':
            # Add version information if we do package-level flow
            self._strict_assert(arguments.get('version'))
            epv['version'] = arguments['version']

        dm_host = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_HOST", "bayesian-data-importer")
        dm_port = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_PORT", "9192")
        dm_endpoint = "api/v1/ingest_to_graph"
        api_url = "http://{host}:{port}/{endpoint}".format(host=dm_host, port=dm_port, endpoint=dm_endpoint)

        self.log.info("Invoke graph importer at url: %s", api_url)
        response = requests.post(api_url, json=[epv])
        response.raise_for_status()
        self.log.info("Graph import succeeded with response: %s", response.text)
