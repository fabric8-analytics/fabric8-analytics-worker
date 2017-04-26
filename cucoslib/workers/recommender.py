from __future__ import division
import json
import requests
import os
from collections import Counter
import re

from cucoslib.graphutils import GREMLIN_SERVER_URL_REST
from cucoslib.base import BaseTask
from cucoslib.conf import get_configuration

config = get_configuration()

danger_word_list = ["drop\(\)", "V\(\)", "count\(\)"]
remove = '|'.join(danger_word_list)
pattern = re.compile(r'(' + remove + ')', re.IGNORECASE)
pattern_to_save = '[^\w\*\.Xx\-\>\=\<\~\^\|\/\:]'
pattern_n2_remove = re.compile(pattern_to_save)


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
        response = requests.post(
            self._bayesian_graph_url, data=json.dumps(payload))
        json_response = response.json()
        if response.status_code != 200:
            return None
        else:
            return json_response

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
        if json_response is not None:
            ref_stack_matching_components = self.get_response_data(json_response, data_default=[])

        # Collect all the stack names
        for sname, val in ref_stack_matching_components[0].items():
            list_stack_names.append(sname)

        # Get total counts of components in reference stacks
        str_gremlin = "g.V().has('vertex_label','Stack').has('sname',within(list_stack_names)).as('stk')" \
                      ".out('has_dependency').select('stk').values('sname').groupCount()"

        payload = {
            'gremlin': str_gremlin,
            'bindings': {
                'list_stack_names': list_stack_names
            }
        }
        json_response = self.execute_gremlin_dsl(payload)
        if json_response is not None:
            ref_stack_full_components = self.get_response_data(json_response, data_default=[])
        ref_stk = {}

        # Calculate similarity score of all reference stacks vs. input stack
        for key, val in ref_stack_matching_components[0].items():
            if key in ref_stack_full_components[0]:
                ref_stk[key] = float(val) / float(ref_stack_full_components[0].get(key))

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
                    'code_complexity': float(component.get('cm_avg_cyclomatic_complexity', [0.0])[0]),
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

    def get_input_stacks_vectors_from_graph(self, input_list, ecosystem):
        """Fetches EPV properties of all the components provided as part of input stack"""
        input_stack_list = []
        for package, version in input_list.items():
            if package is not None:
                payload = {
                    'gremlin': "g.V().has('pecosystem',ecosystem).has('pname',pkg).has('version',version).valueMap();",
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
                            'code_complexity': float(data.get('cm_avg_cyclomatic_complexity', ['0'])[0])
                        }
                    )
        return input_stack_list


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
        """Breaks down reference stack elements into two separate lists of package names and corresponding version"""
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
        Returns the actual distance between input stack EPV and reference stack EPV based on some vectors.
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
        Boost the similarity score if a component is missing from input stack but is part of our reference stack,
        and at the same time is also distributed by redhat.
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

        return additional_downstream/denominator, missing_downstream_component

    def compute_modified_jaccard_similarity(self, len_input_stack, len_ref_stack, vcount):
        """For two stacks A and B, it returns Count(A intersection B) / max(Count(A, B))"""
        return vcount/max(len_ref_stack, len_input_stack)

    def filter_package(self, input_stack, ref_stacks):
        """
        Filters reference stack and process only those which has a higher value of intersection of components
        (Input Stack vs. Reference Stack) based on some configuration param
        """
        input_set = set(list(input_stack.keys()))
        jaccard_threshold = self.jaccard_threshold
        filtered_ref_stacks = []
        for ref_stack in ref_stacks:
            refstack_component_list, corresponding_version = self.get_refstack_component_list(ref_stack)
            refstack_component_set = set(refstack_component_list)
            vcount = len(input_set.intersection(refstack_component_set))
            # Get similarity of input stack w.r.t reference stack
            original_score = RelativeSimilarity().compute_modified_jaccard_similarity(len(input_set),
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
            refstack_component_list, corresponding_version = self.get_refstack_component_list(ref_stack)
            for component, ref_stack_component_version in zip(refstack_component_list, corresponding_version):
                if component in input_stack:
                    input_component_version = input_stack[component]
                    if self.is_same_version(ref_stack_component_version, input_component_version):
                        vcount += 1
                    else:
                        version_mismatch.append({component: ref_stack_component_version})
                        vcount += self.getp_value_graph(component, input_stack_vectors, ref_stack)
                else:
                    missing_packages.append({component: ref_stack_component_version})

            original_score = self.compute_modified_jaccard_similarity(len(input_set), len(refstack_component_list), vcount)

            # Get Downstream Boosting
            # We do not do downstream boosting at the moment
            # boosted_score, missing_downstream_component =  self.downstream_boosting(missing_packages,ref_stack,
            #                                                                        max(len(input_set),len(refstack_component_list)))
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
        rs = RelativeSimilarity()

        input_stack = {d["package"]: d["version"] for d in arguments.get("result", [])[0].get("details", [])[0].get("_resolved")}
        ecosystem = arguments.get("result", [])[0].get("details", [])[0].get("ecosystem")

        # Get Input Stack data
        input_stack_vectors = GraphDB().get_input_stacks_vectors_from_graph(input_stack, ecosystem)
        # Fetch all reference stacks if any one component from input is present
        ref_stacks = GraphDB().get_reference_stacks_from_graph(input_stack.keys())
        # Apply jaccard similarity to consider only stacks having 30% interection of component names
        # We only get one top matching reference stack based on components now
        # filtered_ref_stacks = rs.filter_package(input_stack, ref_stacks)
        # Calculate similarity of the filtered stacks
        similar_stacks_list = rs.find_relative_similarity(input_stack, input_stack_vectors, ref_stacks)
        similarity_list = self._get_stack_values(similar_stacks_list)
        result = {"recommendations": {
            "similar_stacks": similarity_list,
            "component_level": None,
            }
        }
        return result

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
