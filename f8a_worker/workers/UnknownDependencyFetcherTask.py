from __future__ import division
import json
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry


def get_dependency_data(dependency_list):
    ecosystem = "maven"
    dep_pkg_list_unknown = []
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
    print()

    return dep_pkg_list_unknown


class UnknownDependencyFetcherTask(BaseTask):
    def execute(self, arguments):
        #self.log.debug("Arguments passed from dependency_parser: {}".format(arguments))
        print(arguments['dependencies'])
        result = get_dependency_data(arguments['dependencies'])
        return {"result": result}
