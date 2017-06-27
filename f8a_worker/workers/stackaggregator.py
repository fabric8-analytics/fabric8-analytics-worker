"""
Gathers component data from the graph database and aggregate the data to be presented
by stack-analyses endpoint

Output: TBD

"""

import os
import json
import requests

from f8a_worker.conf import get_configuration
from f8a_worker.solver import get_ecosystem_parser
from f8a_worker.base import BaseTask
from f8a_worker.graphutils import (get_stack_usage_data_graph, get_stack_popularity_data_graph,aggregate_stack_data,GREMLIN_SERVER_URL_REST)
from f8a_worker.workers.mercator import MercatorTask
from f8a_worker.utils import get_session_retry

class StackAggregatorTask(BaseTask):
    description = 'Aggregates stack data from components'
    _analysis_name = 'stack_aggregator'

    def _ingest_unknown_dependencies(self, ecosystem, result, resolved):
        unknown_deps = []
        # Initial validation
        if 'components' not in result or len(result['components']) == 0:
            for elem in resolved:
                unknown_deps.append(elem)
                pkg,ver = elem['package'],elem['version']
            return unknown_deps

        # If some of the components are unknown
        deps = {}
        known_deps = {}
        for component in result['components']:
            known_deps[component['name']] = component['version']
        
        for elem in resolved:
            try:
                if known_deps[elem['package']] != elem['version']:
                    self.log.info("Found an unknown dependency {}-{}".format(elem['package'], elem['version']))
                    unknown_deps.append(elem)
            except KeyError:
                self.log.error("Found an unknown dependency {}-{}".format(elem['package'], elem['version']))
                unknown_deps.append(elem)

        # Not right now, but we may have to include unknown dependencies to the schema later
        return unknown_deps

    def _get_dependency_data (self, resolved, ecosystem):
        # Hardcoded ecosystem
        result = []
        for elem in resolved:
            qstring =  "g.V().has('pecosystem','"+ecosystem+"').has('pname','"+elem["package"]+"').has('version','"+elem["version"]+"')."
            qstring += "as('version').in('has_version').as('package').select('version','package').by(valueMap()).dedup();"
            payload = {'gremlin': qstring}

            try:
                graph_req = get_session_retry().post(GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
                if graph_req.status_code == 200:
                    graph_resp = graph_req.json()
                    if 'result' not in graph_resp:
                        continue
                    if len(graph_resp['result']['data']) == 0:
                        continue
                    result.append(graph_resp["result"])
                else:
                    self.log.error("Failed retrieving dependency data.")
                    continue
            except:
                self.log.error("Error retrieving dependency data.")
                continue

        return {"result": result}

    def execute(self, arguments=None):
        finished = []
        aggregated = self.parent_task_result('GraphAggregatorTask')

        for result in aggregated['result']:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']
            manifest = result['details'][0]['manifest_file']

            finished = self._get_dependency_data(resolved,ecosystem)
            if finished != None:
                stack_data = aggregate_stack_data(finished, manifest, ecosystem.lower())
                stack_data['unknown_deps'] = self._ingest_unknown_dependencies(ecosystem, stack_data, resolved)
                return stack_data

        return {}

