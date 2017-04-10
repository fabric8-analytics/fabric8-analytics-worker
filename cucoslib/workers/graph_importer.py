from cucoslib.base import BaseTask
from requests_futures.sessions import FuturesSession
from os import environ
import json

class GraphImporterTask(BaseTask):

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))
 
        ecosystem = arguments.get('ecosystem')
        name = arguments.get('name')
        version = arguments.get('version')

        session = FuturesSession()

        # Initiate data model importer session
        epv = [{ 'ecosystem': ecosystem, 'name': name, 'version': version }]

        dm_host = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_HOST", "bayesian-data-importer")
        dm_port = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_PORT", "9192")
        dm_endpoint = "api/v1/ingest_to_graph"
        api_url = "http://{host}:{port}/{endpoint}".format(host=dm_host, port=dm_port, endpoint=dm_endpoint)

        future = session.post(api_url, json=epv)

