from cucoslib.base import BaseTask
from cucoslib.object_cache import ObjectCache
from cucoslib.models import Analysis, EcosystemBackend, Ecosystem, Version, Package
from cucoslib.utils import get_latest_analysis
from celery.utils.log import get_task_logger

import json
from os import environ
from requests import post


class GraphSyncTask(BaseTask):
    def execute(self, arguments):
        _RETRY_COUNTDOWN = 10

        ecosystem = arguments.get['ecosystem']
        name = arguments.get['name']
        version = arguments.get['version']

        host = environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost")
        port = environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182")
        url = "http://{host}:{port}".format(host=host, port=port)
        # retry until the package data is avaiable in the graphDB
        qstring =  "g.V().has('pecosystem','" + ecosystem + "').has('pname','" + name+"').has('version','" + version + "')."
        qstring += "as('version').in('PackageVersion').as('package').select('version','package').by(valueMap());"
        payload = {'gremlin': qstring}

        graph_req = post(url, json=payload)
        try:
            result = graph_req.json()
            if  len(result.get('result',{}).get('result',{}).get('data', [])) > 0:
                self.log.info("Data for {eco}/{name}/{version} has been published on database".format(eco=ecosystem, name=name, version=version))
            else:
                self.log.info("Package is not yet available on the database. Retrying in a while ...")
                self.retry(self._RETRY_COUNTDOWN)
        except:
            self.log.error("Exception while parsing database response")
            self.retry(self._RETRY_COUNTDOWN)

