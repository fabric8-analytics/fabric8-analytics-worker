"""Sync package data to graph database."""

from requests import post
from f8a_worker.base import BaseTask


class GraphSyncTask(BaseTask):
    """Sync package data to graph database."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        _RETRY_COUNTDOWN = 10

        ecosystem = arguments.get['ecosystem']
        name = arguments.get['name']
        version = arguments.get['version']

        host = self.configuration.BAYESIAN_GREMLIN_HTTP_SERVICE_HOST
        port = self.configuration.BAYESIAN_GREMLIN_HTTP_SERVICE_PORT
        url = "http://{host}:{port}".format(host=host, port=port)
        # retry until the package data is avaiable in the graphDB
        qstring = "g.V().has('pecosystem','" + ecosystem + "').has('pname','" + name + \
                  "').has('version','" + version + "')."
        qstring += "as('version').in('PackageVersion').as('package')." + \
                   "select('version','package').by(valueMap());"
        payload = {'gremlin': qstring}

        graph_req = post(url, json=payload)
        try:
            result = graph_req.json()
            if len(result.get('result', {}).get('result', {}).get('data', [])) > 0:
                self.log.info("Data for {eco}/{name}/{version} has been published "
                              "on database".format(eco=ecosystem, name=name, version=version))
            else:
                self.log.info("Package is not yet available on the database. "
                              "Retrying in a while ...")
                self.retry(_RETRY_COUNTDOWN)
        except Exception:
            self.log.error("Exception while parsing database response")
            self.retry(_RETRY_COUNTDOWN)
