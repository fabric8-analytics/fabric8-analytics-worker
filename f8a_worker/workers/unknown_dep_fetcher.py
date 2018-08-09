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
        dep_pkg_list_unknown = list()
        dep_pkg_list_known = list()
        for dependency in dependency_list:
            n_colons = dependency.count(":")
            dependency_list = dependency.split(":")
            ecosystem = dependency_list[0]
            version = dependency_list[-1]

            if n_colons == 3:
                name = dependency_list[1] + ":" + dependency_list[2]
            elif n_colons == 2:
                name = dependency_list[1]
            else:
                self.log.error("No valid dependency format found: {}"
                               .format(dependency))
                name = ""

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

        self.log.info("Known dependencies are: {}".format(dep_pkg_list_known))
        self.log.info("Unknown dependencies are: {}".format(dep_pkg_list_unknown))
        return dep_pkg_list_unknown

    def execute(self, arguments=None):
        """
        Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from GithubDependencyTreeTask: {}".format(arguments))

        if arguments.get("lock_file_absent"):
            return {"lock_file_absent": arguments.get('lock_file_absent'),
                    "result": [], "message": arguments.get('message')}

        self._strict_assert(arguments.get('dependencies'))
        result = self.get_dependency_data(arguments.get('dependencies'))
        return {"result": result}
