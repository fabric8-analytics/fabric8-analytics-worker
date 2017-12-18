from __future__ import division
import json
import traceback
import datetime

import requests
import os
from collections import Counter, defaultdict
import re
import logging
import semantic_version as sv

from f8a_worker.graphutils import (GREMLIN_SERVER_URL_REST, create_package_dict,
                                   select_latest_version, LICENSE_SCORING_URL_REST)
from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry
from f8a_worker.workers.stackaggregator_v2 import extract_user_stack_package_licenses


danger_word_list = ["drop\(\)", "V\(\)", "count\(\)"]
remove = '|'.join(danger_word_list)
pattern = re.compile(r'(' + remove + ')', re.IGNORECASE)
pattern_to_save = '[^\w\*\.Xx\-\>\=\<\~\^\|\/\:]'
pattern_n2_remove = re.compile(pattern_to_save)

_logger = logging.getLogger(__name__)


class SimilarStack(object):
    def __init__(self, stack_id, usage_score=None, source=None,
                 original_score=None, missing_packages=None,
                 version_mismatch=None, stack_name=None):
        self.stack_id = stack_id
        self.stack_name = stack_name
        self.usage_score = usage_score
        self.source = source
        self.original_score = original_score
        self.missing_packages = missing_packages or []
        self.version_mismatch = version_mismatch or []

    def __repr__(self):
        return '{}: {} {}'.format(self.__class__.__name__,
                                  self.stack_id, self.original_score)


class GraphDB:

    def __init__(self):
        self._bayesian_graph_url = GREMLIN_SERVER_URL_REST

    @staticmethod
    def id_value_checker(id_value):
        """Check is the given id_value is an integer or not"""
        if isinstance(id_value, int):
            return id_value
        return 0

    @staticmethod
    def str_value_cleaner(safe_string):
        """
        Clean up the safe_string to remove suspicious words,
        and special characters.
        """
        result = ''
        if isinstance(safe_string, str):  # can raise an exception as well
            temp_str = pattern.sub('', safe_string)
            result = pattern_n2_remove.sub('', temp_str)
        return result

    def execute_gremlin_dsl(self, payload):
        """Execute the gremlin query and return the response."""
        try:
            response = get_session_retry().post(self._bayesian_graph_url, data=json.dumps(payload))
            if response.status_code != 200:
                _logger.error("HTTP error {}. Error retrieving Gremlin data.".format(
                    response.status_code))
                return None
            else:
                json_response = response.json()
                return json_response
        except Exception:
            _logger.error("Failed retrieving Gremlin data.")
            return None

    def get_response_data(self, json_response, data_default):
        """Data default parameters takes what should data to be returned."""
        return json_response.get("result", {}).get("data", data_default)

    def get_full_ref_stacks(self, list_packages):
        full_ref_stacks = []
        str_packages = []
        for package in list_packages:
            str_packages.append(GraphDB.str_value_cleaner(package))
        str_gremlin = "g.V().has('vertex_label','Version').has('pname',within(str_packages))" \
                      ".in('has_dependency').valueMap(true);"
        payload = {
            'gremlin': str_gremlin,
            'bindings': {
                'str_packages': str_packages
            }
        }
        json_response = self.execute_gremlin_dsl(payload)
        if json_response is not None:
            full_ref_stacks = self.get_response_data(json_response,
                                                     data_default=[])
        return full_ref_stacks

    def get_topmost_ref_stack(self, list_packages):
        """
        Get best matching reference stack in terms of similarity score
        Similarity score is calculated as, given,
        input_stack is a list of package names in manifest file
        ref_stack is a list of package names in a reference stack
        sim_score = count(input_stack intersection ref_stack) / max(len(input_stack, ref_stack))
        """
        str_packages = []
        ref_stack_matching_components = {}
        ref_stack_full_components = {}
        list_stack_names = []
        for package in list_packages:
            str_packages.append(GraphDB.str_value_cleaner(package))

        # Get count of matching components across reference stacks for a given input stack
        str_gremlin = "g.V().has('vertex_label','Version').has('pname',within(str_packages))" \
                      ".in('has_dependency').values('sname').groupCount();"
        payload = {
            'gremlin': str_gremlin,
            'bindings': {
                'str_packages': str_packages
            }
        }
        json_response = self.execute_gremlin_dsl(payload)

        if json_response is None:
            return []

        ref_stack_matching_components = self.get_response_data(json_response, data_default=[])

        # Collect all the stack names
        for sname, val in ref_stack_matching_components[0].items():
            list_stack_names.append(sname)

        # Get total counts of components in reference stacks
        str_gremlin = "g.V().has('vertex_label','Stack').has('sname',within(list_stack_names))" \
                      ".as('stk')" \
                      ".out('has_dependency').select('stk').values('sname').groupCount()"

        payload = {
            'gremlin': str_gremlin,
            'bindings': {
                'list_stack_names': list_stack_names
            }
        }
        json_response = self.execute_gremlin_dsl(payload)
        if len(json_response.get("result", [{}]).get("data", [{}])[0].items()) > 0:
            if json_response is not None:
                ref_stack_full_components = self.get_response_data(json_response, data_default=[])
            ref_stk = {}

            # Calculate similarity score of all reference stacks vs. input stack
            for key, val in ref_stack_matching_components[0].items():
                if key in ref_stack_full_components[0]:
                    denominator = float(max(ref_stack_full_components[0].get(key),
                                        len(list_packages)))
                    ref_stk[key] = float(val) / denominator

            # Get the name of reference stack with topmost similarity score
            sname = max(ref_stk.keys(), key=(lambda key: ref_stk[key]))

            # Get data of reference stack based on sname above
            str_gremlin = "g.V().has('vertex_label','Stack').has('sname', sname).valueMap(true);"

            payload = {
                'gremlin': str_gremlin,
                'bindings': {
                    'sname': sname
                }
            }
            json_response = self.execute_gremlin_dsl(payload)
            if json_response is not None:
                return self.get_response_data(json_response, data_default=[])

        return []

    def get_top_5_ref_stack(self, full_ref_stacks):
        frr = []
        top_ref_stacks = []
        for ref_stack in full_ref_stacks:
            frr.append(ref_stack.get('id'))

        for top_key, value in (dict(Counter(frr).most_common(1))).items():
            for ref_stack in full_ref_stacks:
                if top_key == ref_stack['id']:
                    top_ref_stacks.append(ref_stack)
                    break
        return top_ref_stacks

    def get_ref_stack_component_list(self, refstackid):
        components = []
        payload = {
            'gremlin': "g.V(refstackid).out().valueMap();",
            'bindings': {
                "refstackid":
                str(GraphDB.id_value_checker(refstackid))
            }
        }
        json_response = self.execute_gremlin_dsl(payload)
        if json_response is not None:
            components = self.get_response_data(json_response,
                                                data_default=[])
        return components

    def get_ref_stack_properties(self, ref_stack):
        ref_stack_map = {
            'application_name': ref_stack.get('sname', [''])[0],
            'appstack_id': ref_stack.get('sid', [''])[0],
            'source': ref_stack.get('source', [''])[0],
            'usage': float(ref_stack.get('usage', ['0.0'])[0]),
            'application_description':
                "Generated Stack: " + ref_stack.get('sname', [''])[0]
        }
        return ref_stack_map

    def get_package_info(self, component):
        package = {
                    'package_name': component.get('pname')[0],
                    'version_spec': {'spec': component.get('version', ['Error'])[0]},
                    'loc': float(component.get('cm_loc', [0.0])[0]),
                    'num_files': float(component.get('cm_num_files', [0.0])[0]),
                    'code_complexity': float(component.get('cm_avg_cyclomatic_complexity',
                                             [0.0])[0]),
                    'redistributed_by_redhat': component.get('shipped_as_downstream', [False])[0]
                }
        return package

    def get_reference_stacks_from_graph(self, list_packages):
        """
        This function retrieves a reference stack,
        which has the highest matching component names with an input stack.
        It then fetches EPV properties of
        all the components in that reference stack.
        """
        list_ref_stacks = []

        # full_ref_stacks = self.get_full_ref_stacks(list_packages)
        # if len(full_ref_stacks) == 0:
        #     return []
        #
        # # Get only the  TOP 5 Reference Stacks
        # top_ref_stacks = self.get_top_5_ref_stack(full_ref_stacks)

        top_ref_stacks = self.get_topmost_ref_stack(list_packages)
        if len(top_ref_stacks) == 0:
            return []

        for ref_stack in top_ref_stacks:
            ref_stack_map = self.get_ref_stack_properties(ref_stack)
            refstackid = ref_stack.get('id')
            components = self.get_ref_stack_component_list(refstackid)
            if len(components) == 0:
                return []
            dependencies = []
            for component in components:
                package = self.get_package_info(component)
                dependencies.append(package)
            ref_stack_map['dependencies'] = dependencies
            list_ref_stacks.append(ref_stack_map)

        return list_ref_stacks

    def get_version_information(self, input_list, ecosystem):
        """Fetch the version information for each of the packages
        Also remove EPVs with CVEs and ones not present in Graph
        """
        input_packages = [package for package in input_list]
        str_query = "g.V().has('ecosystem',ecosystem).has('name',within(input_packages))" \
                    ".as('pkg').out('has_version')" \
                    ".hasNot('cve_ids').as('ver').select('pkg','ver').by(valueMap()).dedup()"
        payload = {
            'gremlin': str_query,
            'bindings': {
                'ecosystem': ecosystem,
                'input_packages': input_packages
            }
        }

        # Query Gremlin with packages list to get their version information
        gremlin_response = self.execute_gremlin_dsl(payload)
        if gremlin_response is None:
            return []
        response = self.get_response_data(gremlin_response, [{0: 0}])
        return response

    def filter_versions(self, epv_list, input_stack):
        """First filter fetches only EPVs that
        1. has No CVEs
        2. are Present in Graph
        Apply additional filter based on following. That is sorted based on
        3. Latest Version
        4. Dependents Count in Github Manifest Data
        5. Github Release Date"""

        pkg_dict = defaultdict(dict)
        new_dict = defaultdict(dict)
        filtered_comp_list = []
        for epv in epv_list:
            name = epv.get('pkg', {}).get('name', [''])[0]
            version = epv.get('ver', {}).get('version', [''])[0]
            # needed for maven version like 1.5.2.RELEASE to be converted to
            # 1.5.2-RELEASE for semantic version to work'
            semversion = version.replace('.', '-', 3)
            semversion = semversion.replace('-', '.', 2)
            if name and version:
                # Select Latest Version and add to filter_list if
                # latest version is > current version
                latest_version = select_latest_version(
                    epv.get('pkg').get('libio_latest_version', [''])[0],
                    epv.get('pkg').get('latest_version', [''])[0])
                if latest_version and latest_version == version:
                    try:
                        if sv.SpecItem('>=' + input_stack.get(name, '0.0.0')).match(
                           sv.Version(semversion)):
                            pkg_dict[name]['latest_version'] = latest_version
                            new_dict[name]['latest_version'] = epv.get('ver')
                            new_dict[name]['pkg'] = epv.get('pkg')
                            filtered_comp_list.append(name)
                    except ValueError:
                        pass

                # Check for Dependency Count Attribute. Add Max deps count version
                # if version > current version
                deps_count = epv.get('ver').get('dependents_count', [-1])[0]
                if deps_count > 0:
                    if 'deps_count' not in pkg_dict[name] or \
                       deps_count > pkg_dict[name].get('deps_count', {}).get('deps_count', 0):
                        try:
                            if sv.SpecItem('>=' + input_stack.get(name, '0.0.0')).match(
                               sv.Version(semversion)):
                                pkg_dict[name]['deps_count'] = {"version": version,
                                                                "deps_count": deps_count}
                                new_dict[name]['deps_count'] = epv.get('ver')
                                new_dict[name]['pkg'] = epv.get('pkg')

                                filtered_comp_list.append(name)
                        except ValueError:
                            pass

                # Check for github release date. Add version with most recent github release date
                gh_release_date = epv.get('ver').get('gh_release_date', [0])[0]
                if gh_release_date > 0.0:
                    if 'gh_release_date' not in pkg_dict[name] or \
                       gh_release_date > \
                       pkg_dict[name].get('gh_release_date', {}).get('gh_release_date', 0):
                        try:
                            if sv.SpecItem('>=' + input_stack.get(name, '0.0.0')).match(
                               sv.Version(semversion)):
                                pkg_dict[name]['gh_release_date'] = {
                                    "version": version,
                                    "gh_release_date": gh_release_date}
                                new_dict[name]['gh_release_date'] = epv.get('ver')
                                new_dict[name]['pkg'] = epv.get('pkg')
                                filtered_comp_list.append(name)
                        except ValueError:
                            pass

        new_list = []
        for package, contents in new_dict.items():
            if 'latest_version' in contents:
                new_list.append({"pkg": contents['pkg'], "ver": contents['latest_version']})
            elif 'deps_count' in contents:
                new_list.append({"pkg": contents['pkg'], "ver": contents['deps_count']})
            elif 'gh_release_date' in contents:
                new_list.append({"pkg": contents['pkg'], "ver": contents['gh_release_date']})

        return new_list, filtered_comp_list

    def get_input_stacks_vectors_from_graph(self, input_list, ecosystem):
        """Fetches EPV properties of all the components provided as part of input stack"""
        input_stack_list = []
        for package, version in input_list.items():
            if package is not None:
                payload = {
                    'gremlin': "g.V().has('pecosystem',ecosystem).has('pname',pkg)." +
                               "has('version',version).valueMap();",
                    'bindings': {
                        "ecosystem": GraphDB.str_value_cleaner(ecosystem),
                        "pkg": GraphDB.str_value_cleaner(package),
                        "version": GraphDB.str_value_cleaner(version)
                    }
                }
                json_response = self.execute_gremlin_dsl(payload)
                if json_response is None:
                    return []
                response = self.get_response_data(json_response, [{0: 0}])
                if len(response) > 0:
                    data = response[0]
                    input_stack_list.append({
                            'package_name': package,
                            'version': version,
                            'loc': float(data.get('cm_loc', ['0'])[0]),
                            'num_files': float(data.get('cm_num_files', ['0'])[0]),
                            'code_complexity': float(data.get('cm_avg_cyclomatic_complexity',
                                                              ['0'])[0])
                        }
                    )
        return input_stack_list

    def get_topics_for_alt(self, comp_list, pgm_dict):
        """Gets topics from pgm and associate with filtered versions from Graph"""
        for epv in comp_list:
            name = epv.get('pkg', {}).get('name', [''])[0]
            if name:
                for pgm_pkg_key, pgm_list in pgm_dict.items():
                    for pgm_epv in pgm_list:
                        if name == pgm_epv.get('package_name', ''):
                            epv['pkg']['pgm_topics'] = pgm_epv.get('topic_list', [])

        return comp_list

    def get_topics_for_comp(self, comp_list, pgm_list):
        """Gets topics from pgm and associate with filtered versions from Graph"""
        for epv in comp_list:
            name = epv.get('pkg', {}).get('name', [''])[0]
            if name:
                for pgm_epv in pgm_list:
                    if name == pgm_epv.get('package_name', ''):
                        epv['pkg']['pgm_topics'] = pgm_epv.get('topic_list', [])
                        epv['pkg']['cooccurrence_probability'] = pgm_epv.get(
                            'cooccurrence_probability', 0)

        return comp_list


class RelativeSimilarity:

    def __init__(self):
        self.jaccard_threshold = float(os.environ.get('JACCARD_THRESHOLD', '0.3'))
        self.similarity_score_threshold = float(os.environ.get('SIMILARITY_SCORE_THRESHOLD', '0.3'))

    def is_same_version(self, ref_component_version, input_component_version):
        return ref_component_version.strip() == input_component_version.strip()

    def relative_similarity(self, x, y):
        """Measures the difference between two elements based on some vectors(list of values)"""
        nu = sum(abs(a - b) for a, b in zip(x, y))
        dnu = sum(x) + sum(y)
        if dnu == 0:
            return 0
        diff = nu * 1.0 / dnu
        sim = round(1 - diff, 4)
        return sim

    def get_refstack_component_list(self, ref_stack):
        """Breaks down reference stack elements into two separate lists of
        package names and corresponding version"""
        refstack_component_list = []
        corresponding_version = []
        ref_stack_deps = ref_stack["dependencies"]
        if ref_stack_deps:
            for dependency in ref_stack_deps:
                refstack_component_list.append(dependency['package_name'])
                corresponding_version.append(dependency['version_spec']['spec'])
        return refstack_component_list, corresponding_version

    def get_code_metrics_info(self, comp):
        loc = comp.get('loc', 0)
        num_files = comp.get('num_files', 0)
        code_complexity = comp.get('code_complexity', 0)
        code_metric_data = [loc if loc > 0 else 0,
                            num_files if num_files > 0 else 0,
                            code_complexity if code_complexity > 0 else 0]
        return code_metric_data

    def getp_value_graph(self, component_name, input_stack, ref_stack):
        """
        Returns the actual distance between input stack EPV and reference stack
        EPV based on some vectors.
        It uses relative_similarity to arrive at the distance.
        """
        input_data = [0, 0, 0]
        ref_data = [0, 0, 0]
        for comp in input_stack:
            if comp['package_name'] == component_name:
                input_data = self.get_code_metrics_info(comp)
                break

        for refcomp in ref_stack['dependencies']:
            if refcomp['package_name'] == component_name:
                ref_data = self.get_code_metrics_info(refcomp)
                break

        pvalue = self.relative_similarity(input_data, ref_data)
        return pvalue

    def downstream_boosting(self, missing_packages, ref_stack, denominator):
        """
        Boost the similarity score if a component is missing from input stack
        but is part of our reference stack, and at the same time is also
        distributed by Red Hat.
        """
        additional_downstream = 0.0
        missing_downstream_component = []
        for pkg in missing_packages:
            for package, ver in pkg.items():
                for component in ref_stack['dependencies']:
                    if component['package_name'] == package:
                        if component['redistributed_by_redhat']:
                            additional_downstream += 1.0
                            missing_downstream_component.append({package: ver})

        return additional_downstream / denominator, missing_downstream_component

    def compute_modified_jaccard_similarity(self, len_input_stack, len_ref_stack, vcount):
        """For two stacks A and B, it returns Count(A intersection B) / max(Count(A, B))"""
        return vcount / max(len_ref_stack, len_input_stack)

    def filter_package(self, input_stack, ref_stacks):
        """
        Filters reference stack and process only those which has a higher value
        of intersection of components
        (Input Stack vs. Reference Stack) based on some configuration param
        """
        input_set = set(list(input_stack.keys()))
        jaccard_threshold = self.jaccard_threshold
        filtered_ref_stacks = []
        for ref_stack in ref_stacks:
            refstack_component_list, corresponding_version = \
                self.get_refstack_component_list(ref_stack)
            refstack_component_set = set(refstack_component_list)
            vcount = len(input_set.intersection(refstack_component_set))
            # Get similarity of input stack w.r.t reference stack
            original_score = RelativeSimilarity().compute_modified_jaccard_similarity(
                len(input_set),
                len(refstack_component_list),
                vcount)
            if original_score > self.jaccard_threshold:
                filtered_ref_stacks.append(ref_stack)
        return filtered_ref_stacks

    def find_relative_similarity(self, input_stack, input_stack_vectors, filtered_ref_stacks):
        """Returns the similarity score between an input stack and reference stack"""
        input_set = set(list(input_stack.keys()))
        similar_stack_lists = []
        for ref_stack in filtered_ref_stacks:
            missing_packages = []
            version_mismatch = []
            vcount = 0
            refstack_component_list, corresponding_version = \
                self.get_refstack_component_list(ref_stack)
            for component, ref_stack_component_version in zip(refstack_component_list,
                                                              corresponding_version):
                if component in input_stack:
                    input_component_version = input_stack[component]
                    if self.is_same_version(ref_stack_component_version, input_component_version):
                        vcount += 1
                    else:
                        version_mismatch.append({component: ref_stack_component_version})
                        vcount += self.getp_value_graph(component, input_stack_vectors, ref_stack)
                else:
                    missing_packages.append({component: ref_stack_component_version})

            original_score = self.compute_modified_jaccard_similarity(len(input_set),
                                                                      len(refstack_component_list),
                                                                      vcount)

            # Get Downstream Boosting
            # We do not do downstream boosting at the moment
            # boosted_score, missing_downstream_component =  self.downstream_boosting(
            #    missing_packages,ref_stack,
            #    max(len(input_set),len(refstack_component_list)))
            # downstream_score = original_score + boosted_score

            # We give the result no matter what similarity score is
            if original_score > self.similarity_score_threshold:
                objid = str(ref_stack["appstack_id"])
                stack_name = str(ref_stack["application_name"])
                usage_score = ref_stack["usage"] if "usage" in ref_stack else None
                source = ref_stack["source"] if "source" in ref_stack else None
                similar_stack = SimilarStack(objid, usage_score, source, original_score,
                                             missing_packages, version_mismatch, stack_name)
                similar_stack_lists.append(similar_stack)

        return similar_stack_lists


class RecommendationTask(BaseTask):
    _analysis_name = 'recommendation'
    description = 'Get Recommendation'

    def execute(self, arguments=None):
        arguments = self.parent_task_result('GraphAggregatorTask')
        recommendations = []
        rs = RelativeSimilarity()

        for result in arguments.get('result', []):
            input_stack = {d["package"]: d["version"] for d in result.get("details", [])[0]
                           .get("_resolved")}
            ecosystem = result["details"][0].get("ecosystem")
            manifest_file_path = result["details"][0].get('manifest_file_path')

            # Get Input Stack data
            input_stack_vectors = GraphDB().get_input_stacks_vectors_from_graph(input_stack,
                                                                                ecosystem)
            # Fetch all reference stacks if any one component from input is present
            ref_stacks = GraphDB().get_reference_stacks_from_graph(input_stack.keys())

            if len(ref_stacks) > 0:
                # Apply jaccard similarity to consider only stacks having 30%
                # interection of component names
                # We only get one top matching reference stack based on components now
                # filtered_ref_stacks = rs.filter_package(input_stack, ref_stacks)
                # Calculate similarity of the filtered stacks
                similar_stacks_list = rs.find_relative_similarity(input_stack, input_stack_vectors,
                                                                  ref_stacks)
                similarity_list = self._get_stack_values(similar_stacks_list)
                recommendations.append({
                    "similar_stacks": similarity_list,
                    "component_level": None,
                    "manifest_file_path": manifest_file_path
                })
            else:
                recommendations.append({
                    "similar_stacks": [],
                    "component_level": None,
                    "manifest_file_path": manifest_file_path
                })

        return {"recommendations": recommendations}

    def _get_stack_values(self, similar_stacks_list):
        """Converts the similarity score list to JSON based on the needs"""
        similarity_list = []
        for stack in similar_stacks_list:
            s_stack = {
                "stack_id": stack.stack_id,
                "stack_name": stack.stack_name,
                "similarity": stack.original_score,
                "usage": stack.usage_score,
                "source": stack.source,
                "analysis": {
                    "missing_packages": stack.missing_packages,
                    "version_mismatch": stack.version_mismatch
                }
            }
            similarity_list.append(s_stack)
        return similarity_list


def invoke_license_analysis_service(user_stack_packages, alternate_packages, companion_packages):
    license_url = LICENSE_SCORING_URL_REST + "/api/v1/stack_license"

    payload = {
        "packages": user_stack_packages,
        "alternate_packages": alternate_packages,
        "companion_packages": companion_packages
    }

    json_response = {}
    try:
        lic_response = get_session_retry().post(license_url, data=json.dumps(payload))
        lic_response.raise_for_status()  # raise exception for bad http-status codes
        json_response = lic_response.json()
    except requests.exceptions.RequestException:
        _logger.exception("Unexpected error happened while invoking license analysis!")
        pass

    return json_response


def apply_license_filter(user_stack_components, epv_list_alt, epv_list_com):
    license_score_list_alt = []
    for epv in epv_list_alt:
        license_scoring_input = {
            'package': epv.get('pkg', {}).get('name', [''])[0],
            'version': epv.get('ver', {}).get('version', [''])[0],
            'licenses': epv.get('ver', {}).get('licenses', [])
        }
        license_score_list_alt.append(license_scoring_input)

    license_score_list_com = []
    for epv in epv_list_com:
        license_scoring_input = {
            'package': epv.get('pkg', {}).get('name', [''])[0],
            'version': epv.get('ver', {}).get('version', [''])[0],
            'licenses': epv.get('ver', {}).get('licenses', [])
        }
        license_score_list_com.append(license_scoring_input)

    # Call license scoring to find license filters
    la_output = invoke_license_analysis_service(user_stack_components,
                                                license_score_list_alt,
                                                license_score_list_com)

    conflict_packages_alt = conflict_packages_com = []
    if la_output.get('status') == 'Successful' and la_output.get('license_filter') is not None:
        license_filter = la_output.get('license_filter', {})
        conflict_packages_alt = license_filter.get('alternate_packages', {})\
                                              .get('conflict_packages', [])
        conflict_packages_com = license_filter.get('companion_packages', {})\
                                              .get('conflict_packages', [])

    list_pkg_names_alt = []
    for epv in epv_list_alt[:]:
        name = epv.get('pkg', {}).get('name', [''])[0]
        if name in conflict_packages_alt:
            list_pkg_names_alt.append(name)
            epv_list_alt.remove(epv)

    list_pkg_names_com = []
    for epv in epv_list_com[:]:
        name = epv.get('pkg', {}).get('name', [''])[0]
        if name in conflict_packages_com:
            list_pkg_names_com.append(name)
            epv_list_com.remove(epv)

    output = {
        'filtered_alt_packages_graph': epv_list_alt,
        'filtered_list_pkg_names_alt': list_pkg_names_alt,
        'filtered_comp_packages_graph': epv_list_com,
        'filtered_list_pkg_names_com': list_pkg_names_com
    }
    _logger.info("License Filter output: {}".format(json.dumps(output)))

    return output


class RecommendationV2Task(BaseTask):
    _analysis_name = 'recommendation_v2'
    description = 'Get Recommendation'

    def call_pgm(self, payload):
        """Calls the PGM model with the normalized manifest information to get
        the relevant packages"""
        try:
            # TODO remove hardcodedness for payloads with multiple ecosystems
            if payload and 'ecosystem' in payload[0]:
                PGM_SERVICE_HOST = os.environ.get(
                    "PGM_SERVICE_HOST") + "-" + payload[0]['ecosystem']
                PGM_URL_REST = "http://{host}:{port}".format(
                    host=PGM_SERVICE_HOST,
                    port=os.environ.get("PGM_SERVICE_PORT"))
                pgm_url = PGM_URL_REST + "/api/v1/schemas/kronos_scoring"
                response = get_session_retry().post(pgm_url, json=payload)
                if response.status_code != 200:
                    self.log.error("HTTP error {}. Error retrieving PGM data.".format(
                        response.status_code))
                    return None
                else:
                    json_response = response.json()
                    return json_response
            else:
                self.log.debug('Payload information is not passed in the call, '
                               'Quitting! PGM\'s call')
        except Exception:
            self.log.error("Failed retrieving PGM data.")
            return None

    def execute(self, parguments=None):
        arguments = self.parent_task_result('GraphAggregatorTask')
        results = arguments['result']

        input_task_for_pgm = []
        recommendations = []
        input_stack = {}
        for result in results:
            temp_input_stack = {d["package"]: d["version"] for d in
                                result.get("details", [])[0].get("_resolved")}
            input_stack.update(temp_input_stack)

        for result in results:
            details = result['details'][0]
            resolved = details['_resolved']
            manifest_file_path = details['manifest_file_path']

            self.log.debug(result)
            recommendation = {
                'companion': [],
                'alternate': [],
                'usage_outliers': [],
                'manifest_file_path': manifest_file_path
            }
            new_arr = [r['package'] for r in resolved]
            json_object = {
                'ecosystem': details['ecosystem'],
                'comp_package_count_threshold': int(os.environ.get('MAX_COMPANION_PACKAGES', 5)),
                'alt_package_count_threshold': int(os.environ.get('MAX_ALTERNATE_PACKAGES', 2)),
                'outlier_probability_threshold': float(os.environ.get('OUTLIER_THRESHOLD', 0.6)),
                'unknown_packages_ratio_threshold':
                    float(os.environ.get('UNKNOWN_PACKAGES_THRESHOLD', 0.3)),
                'user_persona': "1",  # TODO - remove janus hardcoded value
                                      # completely and assing a cateogory here
                'package_list': new_arr
            }
            self.log.debug(json_object)
            input_task_for_pgm.append(json_object)

            # Call PGM and get the response
            start = datetime.datetime.utcnow()
            #pgm_response = self.call_pgm(input_task_for_pgm)
            pgm_response = [{'user_persona': '1', 'alternate_packages': {}, 'ecosystem': 'maven', 'companion_packages': [{'cooccurrence_probability': 75, 'package_name': 'mysql:mysql-connector-java', 'topic_list': ['java', 'connector', 'mysql']}, {'cooccurrence_probability': 3, 'package_name': 'org.springframework.boot:spring-boot-starter-web', 'topic_list': ['spring-webapp-booster', 'spring-starter-web', 'spring-rest-api-starter', 'spring-web-service']}, {'cooccurrence_probability': 1, 'package_name': 'org.springframework.boot:spring-boot-starter-data-jpa', 'topic_list': ['spring-persistence', 'spring-jpa', 'spring-data', 'spring-jpa-adaptor']}, {'cooccurrence_probability': 2, 'package_name': 'org.springframework.boot:spring-boot-starter-actuator', 'topic_list': ['spring-rest-api', 'spring-starter', 'spring-actuator', 'spring-http']}], 'missing_packages': [], 'outlier_package_list': [], 'package_to_topic_dict': {'io.vertx:vertx-web': ['vertx-web', 'webapp', 'auth', 'routing'], 'io.vertx:vertx-core': ['http', 'socket', 'tcp', 'reactive']}}]
            elapsed_seconds = (datetime.datetime.utcnow() - start).total_seconds()
            msg = 'It took {t} seconds to get response from PGM ' \
                  'for external request {e}.'.format(t=elapsed_seconds,
                                                     e=parguments.get('external_request_id'))
            self.log.info(msg)

            # From PGM response process companion and alternate packages and
            # then get Data from Graph
            # TODO - implement multiple manifest file support for below loop

            if pgm_response is not None:
                for pgm_result in pgm_response:
                    companion_packages = []
                    ecosystem = pgm_result['ecosystem']

                    # Get usage based outliers
                    recommendation['usage_outliers'] = \
                        pgm_result['outlier_package_list']

                    # Append Topics for User Stack
                    recommendation['input_stack_topics'] = pgm_result.get('package_to_topic_dict',
                                                                          {})

                    for pkg in pgm_result['companion_packages']:
                        companion_packages.append(pkg['package_name'])

                    # Get Companion Packages from Graph
                    comp_packages_graph = GraphDB().get_version_information(companion_packages,
                                                                            ecosystem)

                    # Apply Version Filters
                    filtered_comp_packages_graph, filtered_list = GraphDB().filter_versions(
                        comp_packages_graph, input_stack)

                    filtered_companion_packages = \
                        set(companion_packages).difference(set(filtered_list))
                    _logger.info("Companion Packages Filtered for external_request_id {} {}"
                                 .format(parguments.get('external_request_id', ''),
                                         filtered_companion_packages))

                    # Get the topmost alternate package for each input package

                    # Create intermediate dict to Only Get Top 1 companion
                    # packages for the time being.
                    temp_dict = {}
                    for pkg_name, contents in pgm_result['alternate_packages'].items():
                        pkg = {}
                        for ind in contents:
                            pkg[ind['package_name']] = ind['similarity_score']
                        temp_dict[pkg_name] = pkg

                    final_dict = {}
                    alternate_packages = []
                    for pkg_name, contents in temp_dict.items():
                        # For each input package
                        # Get only the topmost alternate package from a set of
                        # packages based on similarity score
                        top_dict = dict(Counter(contents).most_common(1))
                        for alt_pkg, sim_score in top_dict.items():
                            final_dict[alt_pkg] = {
                                'version': input_stack[pkg_name],
                                'replaces': pkg_name,
                                'similarity_score': sim_score
                            }
                            alternate_packages.append(alt_pkg)

                    # Get Alternate Packages from Graph
                    alt_packages_graph = GraphDB().get_version_information(
                        alternate_packages, ecosystem)

                    # Apply Version Filters
                    filtered_alt_packages_graph, filtered_list = GraphDB().filter_versions(
                        alt_packages_graph, input_stack)

                    filtered_alternate_packages = \
                        set(alternate_packages).difference(set(filtered_list))
                    _logger.info("Alternate Packages Filtered for external_request_id {} {}"
                                 .format(parguments.get('external_request_id', ''),
                                         filtered_alternate_packages))

                    # apply license based filters
                    list_user_stack_comp = extract_user_stack_package_licenses(resolved, ecosystem)
                    license_filter_output = apply_license_filter(list_user_stack_comp,
                                                                 filtered_alt_packages_graph,
                                                                 filtered_comp_packages_graph)

                    lic_filtered_alt_graph = license_filter_output['filtered_alt_packages_graph']
                    lic_filtered_comp_graph = license_filter_output['filtered_comp_packages_graph']
                    lic_filtered_list_alt = license_filter_output['filtered_list_pkg_names_alt']
                    lic_filtered_list_com = license_filter_output['filtered_list_pkg_names_com']

                    if len(lic_filtered_list_alt) > 0:
                        s = set(filtered_alternate_packages).difference(set(lic_filtered_list_alt))
                        msg = \
                            "Alternate Packages filtered (licenses) for external_request_id {} {}"\
                            .format(parguments.get('external_request_id', ''), s)
                        _logger.info(msg)

                    if len(lic_filtered_list_com) > 0:
                        s = set(filtered_companion_packages).difference(set(lic_filtered_list_com))
                        msg = \
                            "Companion Packages filtered (licenses) for external_request_id {} {}"\
                            .format(parguments.get('external_request_id', ''), s)
                        _logger.info(msg)

                    # Get Topics Added to Filtered Packages
                    topics_comp_packages_graph = GraphDB().\
                        get_topics_for_comp(lic_filtered_comp_graph,
                                            pgm_result['companion_packages'])

                    # Create Companion Block
                    comp_packages = create_package_dict(topics_comp_packages_graph)
                    recommendation['companion'] = comp_packages

                    # Get Topics Added to Filtered Packages
                    topics_comp_packages_graph = GraphDB().\
                        get_topics_for_alt(lic_filtered_alt_graph,
                                           pgm_result['alternate_packages'])

                    # Create Alternate Dict
                    alt_packages = create_package_dict(topics_comp_packages_graph, final_dict)
                    recommendation['alternate'] = alt_packages

            recommendations.append(recommendation)
        return {'recommendations': recommendations}
