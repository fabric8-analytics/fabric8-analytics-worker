"""Ingest to graph task."""

from f8a_worker.base import BaseTask
import requests
from os import environ
import logging

logger = logging.getLogger(__name__)

_SERVICE_HOST = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_HOST", "bayesian-data-importer")
_SERVICE_PORT = environ.get("BAYESIAN_DATA_IMPORTER_SERVICE_PORT", "9192")
_SELECTIVE_SERVICE_ENDPOINT = "api/v1/selective_ingest"
_SELECTIVE_API_URL = "http://{host}:{port}/{endpoint}".format(
    host=_SERVICE_HOST,
    port=_SERVICE_PORT,
    endpoint=_SELECTIVE_SERVICE_ENDPOINT)


class NewGraphImporterTask(BaseTask):
    """Ingest to graph node."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        package_list = [
            {
                        'ecosystem': arguments.get('ecosystem'),
                        'name': arguments['name'],
                        'version': arguments.get('version'),
                        'source_repo': arguments.get('ecosystem')
            }
        ]

        param = {
            'select_ingest': ['github_details'],
            'package_list': package_list
        }

        logger.info("v2_:_Invoke graph importer at url: '%s' for %s",
                    _SELECTIVE_API_URL, param)
        # Calling Data Importer API end point to ingest data into graph db.
        response = requests.post(_SELECTIVE_API_URL, json=param)

        if response.status_code != 200:
            raise RuntimeError("v2_:_Failed to invoke graph import at '%s' for %s" %
                               (_SELECTIVE_API_URL, param))

        logger.info("v2_:_Graph import succeeded with response: %s", response.text)
