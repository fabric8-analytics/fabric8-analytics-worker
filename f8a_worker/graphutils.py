"""Miscellaneous functions."""

import os
import logging
import json
import datetime
import semantic_version as sv
import requests
from f8a_worker.utils import get_session_retry
from f8a_worker.defaults import configuration

logger = logging.getLogger(__name__)

GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format(
    host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST"),
    port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT"))

DATA_IMPORTER_URL = 'http://{host}:{port}'.format(
    host=os.environ.get('BAYESIAN_DATA_IMPORTER_SERVICE_HOST'),
    port=os.environ.get('BAYESIAN_DATA_IMPORTER_SERVICE_PORT')
)

LICENSE_SCORING_URL_REST = "http://{host}:{port}".format(
    host=os.environ.get("LICENSE_SERVICE_HOST"),
    port=os.environ.get("LICENSE_SERVICE_PORT"))


def get_stack_usage_data_graph(components):
    """Get average usage for components."""
    components_with_usage_data = 0
    total_dependents_count = 0
    rh_distributed_comp_count = 0
    low_usage_component_count = 0
    for dep in components:
        dependents_count = int(dep.get("package_dependents_count", "-1"))
        if dependents_count > 0:
            if dependents_count < configuration.USAGE_THRESHOLD:
                low_usage_component_count += 1
            total_dependents_count += dependents_count
            components_with_usage_data += 1

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


def get_stack_popularity_data_graph(components):
    """Get average stars/forks for components` github details."""
    components_with_stargazers = 0
    components_with_forks = 0
    total_stargazers = 0
    total_forks = 0
    less_popular_components = 0

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
                if stargazers_count < configuration.POPULARITY_THRESHOLD:
                    less_popular_components += 1

    result = {
        "average_stars": "NA",
        "average_forks": "NA",
        "low_popularity_components": less_popular_components
    }
    if components_with_stargazers > 0:
        result["average_stars"] = "%.2f" % round(
            float(total_stargazers) / components_with_stargazers, 2)

    if components_with_forks > 0:
        result['average_forks'] = "%.2f" % round(
            float(total_forks) / components_with_forks, 2)

    return result


def extract_component_details(component):
    """Extract component details."""
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
        "average_cyclomatic_complexity":
            component.get("version", {}).get("cm_avg_cyclomatic_complexity", [-1])[0],
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

    cves = []
    security = {}
    for cve in component.get("version", {}).get("cve_ids", []):
        component_cve = {
            'id': cve.split(':')[0],
            'cvss': cve.split(':')[1]
        }
        cves.append(component_cve)

    if len(cves) > 0:
        security = {
            "vulnerabilities": cves
        }

    licenses = component.get("version", {}).get("declared_licenses", [])
    name = component.get("version", {}).get("pname", [""])[0]
    version = component.get("version", {}).get("version", [""])[0]
    ecosystem = component.get("version", {}).get("pecosystem", [""])[0]
    latest_version = component.get("package", {}).get("latest_version", [""])[0]
    component_summary = {
        "name": name,
        "version": version,
        "ecosystem": ecosystem,
        "id": ':'.join([ecosystem, name, version]),
        "latest_version": latest_version,
        "github_details": github_details,
        "licenses": licenses,
        "redhat_usage": redhat_usage,
        "code_metrics": code_metrics,
        "security": security
    }
    return component_summary, licenses


def aggregate_stack_data(stack, manifest_file, ecosystem, manifest_file_path):
    """Aggregate stack data."""
    components = []
    licenses = []
    for component in stack.get('result', []):
        data = component.get("data", None)
        if data:
            component_data, component_licenses = extract_component_details(data[0])
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
            "components": components,
            "manifest_file_path": manifest_file_path
    }
    return data


def get_osio_user_count(ecosystem, name, version):
    """Get OSIO user count."""
    str_gremlin = "g.V().has('pecosystem','{}').has('pname','{}').has('version','{}').".format(
        ecosystem, name, version)
    str_gremlin += "in('uses').count();"
    payload = {
        'gremlin': str_gremlin
    }

    try:
        response = get_session_retry().post(GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
        json_response = response.json()
        return json_response['result']['data'][0]
    except Exception:
        logger.error("Failed retrieving Gremlin data.")
        return -1


def create_package_dict(graph_results, alt_dict=None):
    """Convert Graph Results into the Recommendation Dict."""
    pkg_list = []

    for epv in graph_results:
        ecosystem = epv.get('ver', {}).get('pecosystem', [''])[0]
        name = epv.get('ver', {}).get('pname', [''])[0]
        version = epv.get('ver', {}).get('version', [''])[0]
        if ecosystem and name and version:
            # TODO change this logic later to fetch osio_user_count
            osio_user_count = get_osio_user_count(ecosystem, name, version)
            pkg_dict = {
                'ecosystem': ecosystem,
                'name': name,
                'version': version,
                'licenses': epv['ver'].get('declared_licenses', []),
                'latest_version': select_latest_version(
                    epv['pkg'].get('libio_latest_version', [''])[0],
                    epv['pkg'].get('latest_version', [''])[0]),
                'security': [],
                'osio_user_count': osio_user_count,
                'topic_list': epv['pkg'].get('pgm_topics', []),
                'cooccurrence_probability': epv['pkg'].get('cooccurrence_probability', 0),
                'cooccurrence_count': epv['pkg'].get('cooccurrence_count', 0)
            }

            github_dict = {
                'dependent_projects': epv['pkg'].get('libio_dependents_projects', [-1])[0],
                'dependent_repos': epv['pkg'].get('libio_dependents_repos', [-1])[0],
                'used_by': [],
                'total_releases': epv['pkg'].get('libio_total_releases', [-1])[0],
                'latest_release_duration': str(datetime.datetime.fromtimestamp(
                                               epv['pkg'].get('libio_latest_release',
                                                              [1496302486.0])[0])),
                'first_release_date': 'N/A',
                'forks_count': epv['pkg'].get('gh_forks', [-1])[0],
                'stargazers_count': epv['pkg'].get('gh_stargazers', [-1])[0],
                'watchers': epv['pkg'].get('gh_subscribers_count', [-1])[0],
                'contributors': -1,
                'size': 'N/A',
                'issues': {
                    'month': {
                        'closed': epv['pkg'].get('gh_issues_last_month_closed', [-1])[0],
                        'opened': epv['pkg'].get('gh_issues_last_month_opened', [-1])[0]
                    },
                    'year': {
                        'closed': epv['pkg'].get('gh_issues_last_year_closed', [-1])[0],
                        'opened': epv['pkg'].get('gh_issues_last_year_opened', [-1])[0]
                    }
                },
                'pull_requests': {
                    'month': {
                        'closed': epv['pkg'].get('gh_prs_last_month_closed', [-1])[0],
                        'opened': epv['pkg'].get('gh_prs_last_month_opened', [-1])[0]
                    },
                    'year': {
                        'closed': epv['pkg'].get('gh_prs_last_year_closed', [-1])[0],
                        'opened': epv['pkg'].get('gh_prs_last_year_opened', [-1])[0]
                    }
                }
            }
            used_by = epv['pkg'].get("libio_usedby", [])
            used_by_list = []
            for epvs in used_by:
                slc = epvs.split(':')
                used_by_dict = {
                    'name': slc[0],
                    'stars': int(slc[1])
                }
                used_by_list.append(used_by_dict)
            github_dict['used_by'] = used_by_list
            pkg_dict['github'] = github_dict
            pkg_dict['code_metrics'] = {
                "average_cyclomatic_complexity":
                    epv['ver'].get('cm_avg_cyclomatic_complexity', [-1])[0],
                "code_lines": epv['ver'].get('cm_loc', [-1])[0],
                "total_files": epv['ver'].get('cm_num_files', [-1])[0]
            }

            if alt_dict is not None and name in alt_dict:
                pkg_dict['replaces'] = [{
                    'name': alt_dict[name]['replaces'],
                    'version': alt_dict[name]['version']
                }]

            pkg_list.append(pkg_dict)
    return pkg_list


def select_latest_version(libio, anitya):
    """Select latest version from libraries.io or anitya."""
    # anitya does not provide latest version anymore, but it's kept for
    # compatibility
    libio_latest_version = libio if libio else '0.0.0'
    anitya_latest_version = anitya if anitya else '0.0.0'
    libio_latest_version = libio_latest_version.replace('.', '-', 3)
    libio_latest_version = libio_latest_version.replace('-', '.', 2)
    anitya_latest_version = anitya_latest_version.replace('.', '-', 3)
    anitya_latest_version = anitya_latest_version.replace('-', '.', 2)
    try:
        latest_version = libio if libio else ''
        if sv.SpecItem('<' + anitya_latest_version).match(sv.Version(libio_latest_version)):
            latest_version = anitya
    except ValueError:
        latest_version = ''

    return latest_version


def update_properties(ecosystem, package, version, properties):
    """Update properties of given EPV in graph.

    :param ecosystem: str, ecosystem
    :param package: str, package
    :param version: str, version
    :param properties: list, a list of properties to update
    """
    url = DATA_IMPORTER_URL + '/api/v1/vertex/{e}/{p}/{v}/properties'.format(
        e=ecosystem,
        p=package,
        v=version
    )

    payload = {
        'properties': properties
    }
    response = requests.put(url, json=payload)
    if response.status_code == 404:
        # This is OK, we just don't have the component in graph yet
        msg = 'Component {e}/{p}/{v} is not yet in graph'.format(
            e=ecosystem,
            p=package,
            v=version
        )
        logger.warning(msg)

    if response.status_code != 200:
        # This is not OK
        msg = 'Error updating properties for {e}/{p}/{v}: {status} {content}'.format(
            e=ecosystem,
            p=package,
            v=version,
            status=response.status_code,
            content=response.content
        )
        logger.error(msg)


def create_nodes(epv_list):
    """Create nodes in graph for all EPVs in the list.

    :param epv_list: list, list of dictionaries where each dict represents single EPV
    :return: None
    """
    if not epv_list:
        return

    url = DATA_IMPORTER_URL + '/api/v1/create_nodes'

    response = requests.post(url, json=epv_list)

    if response.status_code != 200:
        msg = '{status} Error creating nodes in graph: {content}'.format(
            status=response.status_code,
            content=response.content
        )
        logger.error(msg)
        raise RuntimeError(msg)
