"""
Gathers component data from the graph database and aggregate the data to be presented
by stack-analyses endpoint

Output: TBD

"""

import os
import json
import requests

from f8a_worker.base import BaseTask
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.utils import get_session_retry

def extract_component_details(component):
    component_summary = []
    github_details = {
        "dependent_projects": 10,
        "dependent_repos": 200,
        "total_releases": 21,
        "latest_release_duration": "2 months",
        "first_release_date": "Apr 16, 2010",
        "used_by": [
            {"name": "dep5", "stars": 3021},
            {"name": "dep6", "stars": 523}
        ],
        "forks_count": 23000,

        "issues": {
            "month": {
                "opened": component.get("package", {}).get("gh_issues_opened_last_month", [-1])[0],
                "closed": component.get("package", {}).get("gh_issues_closed_last_month", [-1])[0]
            }, "year": {
                "opened": component.get("package", {}).get("gh_issues_opened_last_year", [-1])[0],
                "closed": component.get("package", {}).get("gh_issues_closed_last_year", [-1])[0]
            }},
        "pull_requests": {
            "month": {
                "opened": component.get("package", {}).get("gh_prs_opened_last_month", [-1])[0],
                "closed": component.get("package", {}).get("gh_prs_closed_last_month", [-1])[0]
            }, "year": {
                "opened": component.get("package", {}).get("gh_prs_opened_last_year", [-1])[0],
                "closed": component.get("package", {}).get("gh_prs_closed_last_year", [-1])[0]
            }},
        "stargazers_count": component.get("package", {}).get("gh_stargazers", [-1])[0],
        "forks_count": component.get("package", {}).get("gh_forks", [-1])[0],
        "watchers": 1673,
        "contributors": 132,
        "size": "4MB"
    }

    code_metrics = {
        "code_lines": component.get("version", {}).get("cm_loc", [-1])[0],
        "average_cyclomatic_complexity": component.get("version", {}).get("cm_avg_cyclomatic_complexity", [-1])[0],
        "total_files": component.get("version", {}).get("cm_num_files", [-1])[0]
    }

    cves = []
    for cve in component.get("version", {}).get("cve_ids", []):
        component_cve = {
            'CVE': cve.split(':')[0],
            'CVSS': cve.split(':')[1]
        }
        cves.append(component_cve)

    licenses = component.get("version", {}).get("licenses", [])
    name = component.get("version", {}).get("pname", [""])[0]
    version = component.get("version", {}).get("version", [""])[0]
    ecosystem = component.get("version", {}).get("pecosystem", [""])[0]
    latest_version = component.get("package", {}).get("latest_version", [""])[0]
    component_summary = {
        "ecosystem": ecosystem,
        "name": name,
        "version": version,
        "licenses": licenses,
        "sentiment": { "overall_score": 1, "latest_comment": '' },
        "security": cves,
        "osio_user_count": 641,
        "latest_version": latest_version,
        "github": github_details,
        "code_metrics": code_metrics
    }
    return component_summary, licenses

def aggregate_stack_data(stack, manifest_file, ecosystem, deps):
    dependencies = []
    licenses = []
    for component in stack.get('result', []):
        data = component.get("data", None)
        if data:
            component_data, component_licenses = extract_component_details(data[0])
            dependencies.append(component_data)
            licenses.extend(component_licenses)

    stack_distinct_licenses = set(licenses)
    data = {
            "manifest_name": manifest_file,
            "user_stack_info": {
                "ecosystem": ecosystem,
                "analyzed_dependencies_count": len(dependencies),
                "analyzed_dependencies": deps,
                "unknown_dependencies_count": 0,
                "unknown_dependencies": [],
                "recommendation_ready": True, #based on the percentage of dependecies analysed
                "total_licenses": len(stack_distinct_licenses),
                "distinct_licenses": list(stack_distinct_licenses),
                "stack_license_conflict": False,
                "dependencies": dependencies
            }
    }
    return data

class StackAggregatorV2Task(BaseTask):
    description = 'Aggregates stack data from components'
    _analysis_name = 'stack_aggregator_v2'

    def _get_dependency_data (self, resolved, ecosystem):
        # Hardcoded ecosystem
        result = []
        for elem in resolved:
            qstring =  "g.V().has('pecosystem','"+ecosystem+"').has('pname','"+elem["package"]+"').has('version','"+elem["version"]+"')."
            qstring += "as('version').in('has_version').as('package').select('version','package').by(valueMap());"
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
                stack_data = aggregate_stack_data(finished, manifest, ecosystem.lower(), resolved)
                print (json.dumps(stack_data))
                return stack_data

        return {}

