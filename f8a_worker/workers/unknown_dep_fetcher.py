"""Task to fetch unknown dependencies."""

from __future__ import division
import json
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry


class UnknownDependencyFetcherTask(BaseTask):
    """Task to fetch unknown dependencies."""

    _analysis_name = 'unknown_deps_fetcher'
    description = 'Fetch unknown dependencies'

    def get_dependency_data(self, dependency_list):
        """Prepare list of unknown dependencies from given list of dependencies."""
        ecosystem = "maven"
        dep_pkg_list_unknown = ['maven:org.apache.maven.resolver:maven-resolver-transport-wagon:1.0.3']
        dep_pkg_list_known = []
        for item in dependency_list:
            dependency_list = item.split(":")
            result = []
            name = dependency_list[0] + ":" + dependency_list[1]
            version = dependency_list[2]
            qstring = ("g.V().has('pecosystem','" + ecosystem + "').has('pname','" +
                       name + "').has('version','" + version + "').tryNext()")
            payload = {'gremlin': qstring}

            graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
            if graph_req.status_code == 200:
                graph_resp = graph_req.json()
                if graph_resp.get('result', {}).get('data'):
                    result.append(graph_resp["result"])
                    if result[0]['data'][0]['present']:
                        dep_pkg_list_known.append(ecosystem + ":" + name + ":" + version)
                    elif not (result[0]['data'][0]['present']):
                        dep_pkg_list_unknown.append(ecosystem + ":" + name + ":" + version)
                    else:
                        continue
                else:
                    continue
        return dep_pkg_list_unknown

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        aggregated = self.parent_task_result('GithubDependencyTreeTask')

        self.log.info("Arguments passed from GithubDependencyTreeTask: {}".format(arguments))
        self.log.info("Result returned by GithubDependencyTreeTask: {}".format(aggregated))

        result = self.get_dependency_data(aggregated['dependencies'])
        return {"result": result}
