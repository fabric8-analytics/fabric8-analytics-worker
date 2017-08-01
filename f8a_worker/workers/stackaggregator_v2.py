"""
Gathers component data from the graph database and aggregate the data to be presented
by stack-analyses endpoint

Output: TBD

"""

import json
import datetime

from f8a_worker.base import BaseTask
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST, LICENSE_SCORING_URL_REST
from f8a_worker.utils import get_session_retry

import logging

def extract_component_details(component):
    github_details = {
        "dependent_projects": component.get("package", {}).get("libio_dependents_projects", [-1])[0],
        "dependent_repos": component.get("package", {}).get("libio_dependents_repos", [-1])[0],
        "total_releases": component.get("package", {}).get("libio_total_releases", [-1])[0],
        "latest_release_duration":
            str(datetime.datetime.fromtimestamp(component.get("package", {}).get("libio_latest_release", [1496302486.0])[0])),
        "first_release_date": "Apr 16, 2010",
        "issues": {
            "month": {
                "opened": component.get("package", {}).get("gh_issues_last_month_opened", [-1])[0],
                "closed": component.get("package", {}).get("gh_issues_last_month_closed", [-1])[0]
            }, "year": {
                "opened": component.get("package", {}).get("gh_issues_last_year_opened", [-1])[0],
                "closed": component.get("package", {}).get("gh_issues_last_year_closed", [-1])[0]
            }},
        "pull_requests": {
            "month": {
                "opened": component.get("package", {}).get("gh_prs_last_month_opened", [-1])[0],
                "closed": component.get("package", {}).get("gh_prs_last_month_closed", [-1])[0]
            }, "year": {
                "opened": component.get("package", {}).get("gh_prs_last_year_opened", [-1])[0],
                "closed": component.get("package", {}).get("gh_prs_last_year_closed", [-1])[0]
            }},
        "stargazers_count": component.get("package", {}).get("gh_stargazers", [-1])[0],
        "forks_count": component.get("package", {}).get("gh_forks", [-1])[0],
        "watchers": 1673,
        "contributors": 132,
        "size": "4MB"
    }
    used_by = component.get("package", {}).get("libio_usedby", [])
    used_by_list = []
    for epvs in used_by:
        slc = epvs.split(':')
        used_by_dict = {
            'name': slc[0],
            'stars': int(slc[1])
        }
        used_by_list.append(used_by_dict)
    github_details['used_by'] = used_by_list

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
        "sentiment": {"overall_score": 1, "latest_comment": ''},
        "security": cves,
        "osio_user_count": component.get("version", {}).get("osio_usage_count", 0),
        "latest_version": latest_version,
        "github": github_details,
        "code_metrics": code_metrics
    }

    return component_summary


def aggregate_stack_data(stack, manifest_file, ecosystem, deps):
    dependencies = []
    licenses = []
    license_score_list = []
    for component in stack.get('result', []):
        data = component.get("data", None)
        if data:
            component_data = extract_component_details(data[0])
            # create license dict for license scoring
            license_scoring_input = {
                'package': component_data['name'],
                'version': component_data['version'],
                'license': component_data['licenses']
            }
            dependencies.append(component_data)
            licenses.extend(component_data['licenses'])
            license_score_list.append(license_scoring_input)

    stack_distinct_licenses = set(licenses)
    # Call License Scoring to Get Stack License

    license_url = LICENSE_SCORING_URL_REST + "/api/v1/stack_license"

    payload = {
        "packages": license_score_list
    }

    _logger = logging.getLogger(__name__)

    try:
        license_req = get_session_retry().post(license_url, data=json.dumps(payload))
        resp = license_req.json()
        
        stack_license_exists = resp.get("stack_license_exists") 
        package_with_unknown_license_exists = resp.get("package_with_unknown_license_exists")
        stack_license_conflict_exists = resp.get("stack_license_conflict_exists")
        package_license_conflict_exists = resp.get("package_license_conflict_exists")
        packages_with_license_conflict = resp.get("packages_with_license_conflict")
        recommended_stack_licenses = resp.get("recommended_stack_licenses")
        stack_license_conflict_packages = resp.get("stack_license_conflict_packages")
        stack_license_outlier_packages = resp.get("stack_license_outlier_packages")

    except:
        _logger.error("Error getting data from Stack License API")

        #Construct default response if API has issues
        stack_license_exists = False 
        package_with_unknown_license_exists = True
        stack_license_conflict_exists = True
        package_license_conflict_exists = True
        packages_with_license_conflict = [None]
        recommended_stack_licenses = [None]
        stack_license_conflict_packages = [None]
        stack_license_outlier_packages = [None]


    data = {
            "manifest_name": manifest_file,
            "user_stack_info": {
                "ecosystem": ecosystem,
                "analyzed_dependencies_count": len(dependencies),
                "analyzed_dependencies": deps,
                "unknown_dependencies_count": 0,
                "unknown_dependencies": [],
                "recommendation_ready": True,  # based on the percentage of dependencies analysed
                "total_licenses": len(stack_distinct_licenses),
                "distinct_licenses": list(stack_distinct_licenses),
                "dependencies": dependencies,
                "stack_license_exists":stack_license_exists, # Does stack license exist
                "package_with_unknown_license_exists": package_with_unknown_license_exists, # Are there unknown licenses
                "stack_license_conflict_exists": stack_license_conflict_exists, # Is there a license conflict amongst packages
                "package_license_conflict_exists": package_license_conflict_exists, # Is there a license conflict within a package
                "packages_with_license_conflict": packages_with_license_conflict, # Packages with license conflict
                "recommended_stack_licenses": recommended_stack_licenses, # stack license
                "stack_license_conflict_packages": stack_license_conflict_packages, # packages causing license conflict
                "stack_license_outlier_packages": stack_license_outlier_packages # Outlier packages for license
            }
    }

    return data


class StackAggregatorV2Task(BaseTask):
    description = 'Aggregates stack data from components'
    _analysis_name = 'stack_aggregator_v2'

    def _get_dependency_data(self, resolved, ecosystem):
        # Hardcoded ecosystem
        result = []
        for elem in resolved:
            qstring = "g.V().has('pecosystem','"+ecosystem+"').has('pname','"+elem["package"]+"')." \
                      "has('version','"+elem["version"]+"')." \
                      "as('version').in('has_version').as('package').select('version','package').by(valueMap());"
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
        aggregated = self.parent_task_result('GraphAggregatorTask')

        for result in aggregated['result']:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']
            manifest = result['details'][0]['manifest_file']

            finished = self._get_dependency_data(resolved, ecosystem)
            if finished is not None:
                stack_data = aggregate_stack_data(finished, manifest, ecosystem.lower(), resolved)
                return stack_data

        return {}
