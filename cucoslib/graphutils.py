import os
import logging

logger = logging.getLogger(__name__)

GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format\
                            (host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost"),\
                            port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182"))

def get_stack_usage_data_graph(components):
    components_with_usage_data = 0
    total_dependents_count = 0
    rh_distributed_comp_count = 0
    usage_threshold = 0
    try:
        usage_threshold = int(os.getenv("LOW_USAGE_THRESHOLD", "5000"))
    except:
        # low usage threshold is set to default 5000 as the env variable value is non numeric
        usage_threshold = 5000
    low_usage_component_count = 0
    for dep in components:
        dependents_count = int(dep.get("package_dependents_count", "-1"))
        if dependents_count > 0:
            if dependents_count < usage_threshold:
                low_usage_component_count += 1
            total_dependents_count += dependents_count
            components_with_usage_data += 1

        rh_distros = dep.get("redhat_usage", {}).get("published_in", [])
        if len(rh_distros) > 0:
            rh_distributed_comp_count += 1

    result = {}
    if components_with_usage_data > 0:
        result['average_usage'] = "%.2f" % round(total_dependents_count / components_with_usage_data, 2)
    else:
        result['average_usage'] = 'NA'
    result['low_public_usage_components'] = low_usage_component_count
    result['redhat_distributed_components'] = rh_distributed_comp_count

    return result


def get_stack_popularity_data_graph(components):
    components_with_stargazers = 0
    components_with_forks = 0
    total_stargazers = 0
    total_forks = 0
    popularity_threshold = 0  # based on stargazers count as of now
    less_popular_components = 0
    try:
        popularity_threshold = int(os.getenv("LOW_POPULARITY_THRESHOLD", "5000"))
    except:
        # low usage threshold is set to default 5000 as the env variable value is non numeric
        popularity_threshold = 5000

    for dep in components:
        gh_data = dep.get("github_details", {})
        if gh_data:
            forks_count = int(gh_data.get("forks_count", "-1"))
            stargazers_count = int(gh_data.get("stargazers_count", "-1"))
            if forks_count > 0:
                total_forks += forks_count
                components_with_forks += 1

            if stargazers_count > 0:
                total_stargazers += stargazers_count
                components_with_stargazers += 1
                if stargazers_count < popularity_threshold:
                    less_popular_components += 1

    result = {}
    if components_with_stargazers > 0:
        result["average_stars"] = "%.2f" % round(total_stargazers / components_with_stargazers, 2)
    else:
        result["average_stars"] = 'NA'

    if components_with_forks > 0:
        result['average_forks'] = "%.2f" % round(total_forks / components_with_forks, 2)
    else:
        result['average_forks'] = 'NA'
    result['low_popularity_components'] = less_popular_components

    return result

def extract_component_details(component):
    component_summary = []
    github_details = {
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
        "forks_count": component.get("package", {}).get("gh_forks", [-1])[0]
    }

    code_metrics = {
        "code_lines": component.get("version", {}).get("cm_loc", [-1])[0],
        "average_cyclomatic_complexity": component.get("version", {}).get("cm_avg_cyclomatic_complexity", [-1])[0],
        "total_files": component.get("version", {}).get("cm_num_files", [-1])[0]
    }
    
    redhat_usage = {
        "all_rhn_channels": [],
        "all_rhsm_content_sets": [],
        "all_rhsm_product_names": component.get("version", {}).get("is_packaged_in", []),
        "package_names": [],
        "registered_srpms": [],
        "rh_mvn_matched_versions": [],
        "published_in": component.get("version", {}).get("is_published_in", [])
    }

    licenses = component.get("version", {}).get("licenses", [])
    name = component.get("version", {}).get("pname", [""])[0]
    version = component.get("version", {}).get("version", [""])[0]
    ecosystem = component.get("version", {}).get("pecosystem", [""])[0]
    latest_version = component.get("package", {}).get ("latest_version",[""])[0]
    component_summary = {
        "name": name,
        "version": version,
        "ecosystem": ecosystem,
        "id": ':'.join([ecosystem, name, version]),
        "latest_version": latest_version,
        "github_details": github_details,
        "licenses": licenses,
        "redhat_usage": redhat_usage,
        "code_metrics": code_metrics
    }
    return component_summary,licenses

def aggregate_stack_data(stack, manifest_file, ecosystem):
    components = []
    licenses = []
    for component in stack.get('result', []):
        data = component.get("data", None)
        if data:
            component_data,component_licenses = extract_component_details(data[0])
            components.append(component_data)
            licenses.extend(component_licenses)

    stack_popularity_data = get_stack_popularity_data_graph(components)
    stack_distinct_licenses = set(licenses)
    data = {
            "manifest_name": manifest_file,
            "ecosystem": ecosystem,
            "analyzed_components": len(components),
            "total_licenses": len(stack_distinct_licenses),
            "distinct_licenses": list(stack_distinct_licenses),
            "popularity": stack_popularity_data,
            "components": components
    }
    return data

