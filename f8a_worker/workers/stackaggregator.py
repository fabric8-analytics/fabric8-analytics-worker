"""
Gathers component data from the graph database and aggregate the data to be presented
by stack-analyses endpoint

Output: TBD

"""

import os
import json
import requests

from f8a_worker.solver import get_ecosystem_parser
from f8a_worker.base import BaseTask
from f8a_worker.graphutils import (get_stack_usage_data_graph, get_stack_popularity_data_graph,
                                   aggregate_stack_data, GREMLIN_SERVER_URL_REST)
from f8a_worker.workers.mercator import MercatorTask
from f8a_worker.utils import get_session_retry


class StackAggregatorTask(BaseTask):
    """ Aggregates stack data from components """
    _analysis_name = 'stack_aggregator'

    def _get_stack_usage_data(self, components):
        components_with_usage_data = 0
        total_dependents_count = 0
        rh_distributed_comp_count = 0
        low_usage_component_count = 0

        for dep in components:
            dependents_count = 0
            try:
                dependents_count = int(dep.get("package_dependents_count", -1))
            except (TypeError, ValueError):
                self.log.debug("Unexpected non-numeric value received for "
                               "package_dependents_count.")
            else:
                if dependents_count > 0:
                    if dependents_count < self.configuration.USAGE_THRESHOLD:
                        low_usage_component_count += 1
                    total_dependents_count += dependents_count
                    components_with_usage_data += 1
            finally:
                rh_distros = dep.get("redhat_usage", {}).get("published_in", [])
                if len(rh_distros) > 0:
                    rh_distributed_comp_count += 1

        result = {}
        if components_with_usage_data > 0:
            result['average_usage'] = "%.2f" % round(total_dependents_count /
                                                     components_with_usage_data, 2)

        else:
            result['average_usage'] = 'NA'

        result['low_public_usage_components'] = low_usage_component_count
        result['redhat_distributed_components'] = rh_distributed_comp_count

        return result

    def _get_stack_popularity_data(self, components):
        components_with_stargazers = 0
        components_with_forks = 0
        total_stargazers = 0
        total_forks = 0
        less_popular_components = 0

        for dep in components:
            gh_data = dep.get("github_details", {}).get("details", {})
            if gh_data:
                try:
                    forks_count = int(gh_data.get("forks_count", -1))
                    stargazers_count = int(gh_data.get("stargazers_count", -1))
                except (TypeError, ValueError):
                    continue
                if forks_count > 0:
                    total_forks += forks_count
                    components_with_forks += 1

                if stargazers_count > 0:
                    total_stargazers += stargazers_count
                    components_with_stargazers += 1
                    if stargazers_count < self.configuration.POPULARITY_THRESHOLD:
                        less_popular_components += 1

        result = {}
        if components_with_stargazers > 0:
            result["average_stars"] = "%.2f" % round(
                total_stargazers / components_with_stargazers, 2)
        else:
            result["average_stars"] = 'NA'

        if components_with_forks > 0:
            result['average_forks'] = "%.2f" % round(total_forks / components_with_forks, 2)
        else:
            result['average_forks'] = 'NA'
        result['low_popularity_components'] = less_popular_components

        return result

    def _get_stack_metadata(self, components, ecosystem_name):
        components_with_tests = 0
        stack_engines = []
        components_with_dependency_lock_file = 0
        dependency_parser = get_ecosystem_parser(self.storage.get_ecosystem(ecosystem_name))
        for dep in components:
            metadata_details = dep.get('metadata', {}).get('details', [])
            if not metadata_details:
                continue
            metadata_details = metadata_details[0]
            if metadata_details.get('_tests_implemented'):
                components_with_tests += 1
            if metadata_details.get('engines'):
                for engine, version_spec in metadata_details['engines'].items():
                    stack_engines += dependency_parser.parse([engine + " " + version_spec])
            if metadata_details.get(MercatorTask._dependency_tree_lock) is not None:
                components_with_dependency_lock_file += 1

        if stack_engines and dependency_parser:
            # keep only the most restricted version specs
            stack_engines = dependency_parser.restrict_versions(stack_engines)

        result = {'components_with_tests': components_with_tests,
                  'required_engines': dependency_parser.compose(stack_engines),
                  'components_with_dependency_lock_file': components_with_dependency_lock_file}
        return result

    def _get_dependency_data(self, resolved, ecosystem):
        # Hardcoded ecosystem
        result = []
        for elem in resolved:
            qstring = ("g.V().has('pecosystem','" + ecosystem + "').has('pname','" +
                       elem["package"] + "').has('version','" + elem["version"] + "').")
            qstring += ("as('version').in('has_version').as('package')." +
                        "select('version','package').by(valueMap());")
            payload = {'gremlin': qstring}

            try:
                graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST,
                                                     data=json.dumps(payload))
                if graph_req.status_code == 200:
                    graph_resp = graph_req.json()
                    if graph_resp.get('result', {}).get('data'):
                        result.append(graph_resp["result"])
                else:
                    self.log.error("Failed retrieving dependency data.")
                    continue
            except Exception:
                self.log.exception("Error retrieving dependency data.")
                continue

        return {"result": result}

    def execute(self, arguments=None):
        stack_data = []

        for result in self.parent_task_result('GraphAggregatorTask')['result']:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']
            manifest = result['details'][0]['manifest_file']
            manifest_file_path = result['details'][0]['manifest_file_path']

            finished = self._get_dependency_data(resolved, ecosystem)
            if finished is not None:
                stack_data.append(aggregate_stack_data(finished, manifest, ecosystem.lower(),
                                                       manifest_file_path))

        return {"stack_data": stack_data}
