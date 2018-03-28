"""Output: TBD."""

import json
import operator
from time import gmtime, strftime

from f8a_worker.base import BaseTask
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.utils import get_session_retry


class ReportGenerationTask(BaseTask):
    """Generates report containing descriptive data for dependencies."""

    def parse_version_data(self, data):
        """
        Parse version data extracted from graph for a given dependency.

        :param data: version data extracted from graph
        :return: parsed version data
        """
        self.log.debug("Version data received is: {}".format(data))
        version = data.get('version', [''])[0]
        cve_ids = data.get('cve_ids', [])
        licenses = data.get('licenses', [])
        cve_list = list()
        for cve_id in cve_ids:
            cve_name, cvss_score = cve_id.split(":")
            cve_list.append((cve_name, float(cvss_score)))
        cve_list.sort(key=operator.itemgetter(1), reverse=True)
        version_data = {"version": version, "cve_count": len(cve_ids), "licenses": licenses}

        if cve_list:
            version_data.update({"cve_id_for_highest_cvss_score": cve_list[0][0],
                                 "highest_cvss_score": cve_list[0][1],
                                 "cves": [x[0] for x in cve_list]})

        self.log.debug("Parsed version data is: {}".format(version_data))
        return version_data

    def parse_package_data(self, data):
        """
        Parse package data extracted from graph for a given dependency.

        :param data: package data extracted from graph
        :return: parsed package data
        """
        self.log.debug("Package data received is: {}".format(data))
        name = data.get('name', [''])[0]
        package_data = {"name": name}
        # Removed latest_version_logic as of now. Might want to add it back in future.
        self.log.debug("Parsed package data is: {}".format(package_data))
        return package_data

    def _get_dependency_data(self, dependencies):
        dependency_data_list = list()
        self.log.debug("Dependencies are: {}".format(dependencies))
        for dependency in dependencies:
            self.log.info("Analyzing dependency: {}".format(dependency))
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
                       name + "')"".has('version','" + version + "').")
            qstring += ("as('version').in('has_version').as('package').dedup()." +
                        "select('version','package').by(valueMap());")
            payload = {'gremlin': qstring}
            try:
                graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST,
                                                     data=json.dumps(payload))
                if graph_req.status_code == 200:
                    graph_resp = graph_req.json()
                    data = graph_resp.get('result', {}).get('data')
                    if data:
                        version_data = self.parse_version_data(data[0].get('version'))
                        package_data = self.parse_package_data(data[0].get('package'))
                        dependency_data = version_data.copy()
                        dependency_data.update(package_data)
                        dependency_data_list.append(dependency_data)
                else:
                    self.log.error("Failed retrieving dependency data.")
                    continue
            except Exception:
                self.log.exception("Error retrieving dependency data.")
                continue

        self.log.debug("Dependency data list is: {}".format(dependency_data_list))
        return dependency_data_list

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from flow: {}".format(arguments))
        self._strict_assert(arguments.get('dependencies'))
        self._strict_assert(arguments.get('github_sha'))
        self._strict_assert(arguments.get('github_repo'))
        resolved_dependencies = arguments.get('dependencies')
        self.log.debug("Resolved dependencies are: {}".format(resolved_dependencies))
        dependency_list = self._get_dependency_data(dependencies=resolved_dependencies)
        self.log.debug("Result returned by Report Generation task is: {}".format(dependency_list))
        arguments.update({"external_request_id": arguments.get('github_sha')})
        return {"dependencies": dependency_list, "git_url": arguments.get('github_repo'),
                "git_sha": arguments.get("github_sha"),
                "scanned_at": strftime("%Y-%m-%dT%H:%M:%S", gmtime())}
