"""Task to fetch unknown dependencies."""

from __future__ import division
import json
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry


class UnknownDependencyFetcherTask(BaseTask):
    """Task to fetch unknown dependencies."""

    def get_dependency_data(self, dependency_list):
        """Prepare list of unknown dependencies from given list of dependencies."""
        ecosystem = "maven"
        dep_pkg_list_unknown = list()
        dep_pkg_list_known = list()
        for dependency in dependency_list:
            dependency_list = dependency.split(":")
            name = dependency_list[0] + ":" + dependency_list[1]
            version = dependency_list[2]
            qstring = ("g.V().has('pecosystem','" + ecosystem + "').has('pname','" +
                       name + "').has('version','" + version + "').tryNext()")
            payload = {'gremlin': qstring}

            graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
            if graph_req.status_code == 200:
                graph_resp_data = graph_req.json().get('result', {}).get('data')
                if graph_resp_data[0].get('present'):
                    dep_pkg_list_known.append(ecosystem + ":" + name + ":" + version)
                else:
                    dep_pkg_list_unknown.append(ecosystem + ":" + name + ":" + version)
            else:
                self.log.error("Error response from graph for {dependency} " +
                               "with status code as {status_code}"
                               .format(dependency=dependency, status_code=graph_req.status_code))

        self.log.debug("Known dependencies are: {}".format(dep_pkg_list_known))
        self.log.debug("Unknown dependencies are: {}".format(dep_pkg_list_unknown))
        return dep_pkg_list_unknown

    def execute(self, arguments=None):
        """
        Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from GithubDependencyTreeTask: {}".format(arguments))
        self._strict_assert(arguments.get('dependencies'))
        result = self.get_dependency_data(arguments.get('dependencies'))
        return {"result": result}
