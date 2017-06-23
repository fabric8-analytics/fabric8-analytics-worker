import os
import json
from shutil import rmtree
from selinon import FatalTaskError
from tempfile import mkdtemp
from cucoslib.solver import get_ecosystem_solver
from cucoslib.base import BaseTask
from cucoslib.manifests import get_manifest_descriptor_by_filename

from cucoslib.workers.mercator import MercatorTask
from selinon import StoragePool

class GraphAggregatorTask(BaseTask):
    _analysis_name = 'graph_aggregator'
    schema_ref = None

    def _handle_external_deps(self, ecosystem, deps):
        """Resolve external dependency specifications"""
        if not ecosystem or not deps:
            return []
        solver = get_ecosystem_solver(ecosystem)
        versions = solver.solve(deps)
        return [{"package": k, "version": v} for k, v in versions.items()]

    def store_in_bucket(self, content):
        s3 = StoragePool.get_connected_storage('S3UserProfileStore')
        s3.store_in_bucket(content)

    def execute(self, arguments):
        self._strict_assert(arguments.get('manifest'))
        self._strict_assert(arguments.get('user_profile'))

        user_profile = arguments['user_profile']
        self.store_in_bucket(user_profile)

        # If we receive a manifest file we need to save it first
        result = []
        for manifest in arguments['manifest']:
            temp_path = mkdtemp()

            with open(os.path.join(temp_path, manifest['filename']), 'a+') as fd:
                fd.write(manifest['content'])

            # mercator-go does not work if there is no package.json
            if 'shrinkwrap' in manifest['filename'].lower():
                with open(os.path.join(temp_path, 'package.json'), 'w') as f:
                    f.write(json.dumps({}))

            # TODO: this is a workaround since stack analysis is not handled by dispatcher, so we create instance manually for now
            subtask = MercatorTask(None, None, None, None, None)
            # since we're creating MercatorTask dynamically in code, we need to make sure
            #  that it has storage; storage is assigned to tasks dynamically based on task_name
            subtask.task_name = self.task_name
            arguments['ecosystem'] = manifest['ecosystem']
            out = subtask.run_mercator(arguments, temp_path)

            if temp_path:
                rmtree(temp_path, ignore_errors=True)
            if not out["details"]:
                raise FatalTaskError("No metadata found processing manifest file '{}'"
                                     .format(manifest['filename']))
            out["details"][0]['manifest_file'] = manifest['filename']
            out["details"][0]['ecosystem'] = manifest['ecosystem']

            # If we're handling an external request we need to convert dependency specifications to
            # concrete versions that we can query later on in the `AggregatorTask`
            manifest_descriptor = get_manifest_descriptor_by_filename(manifest['filename'])
            if 'external_request_id' in arguments:
                if manifest_descriptor.has_resolved_deps:  # npm-shrinkwrap.json, pom.xml, requirements.txt
                    if "_dependency_tree_lock" in out["details"][0]:  # npm-shrinkwrap.json, requirements.txt
                        manifest_dependencies = out["details"][0]["_dependency_tree_lock"]["dependencies"]
                    else:  # pom.xml
                        manifest_dependencies = out["details"][0]["dependencies"]
                    if manifest_descriptor.has_recursive_deps:  # npm-shrinkwrap.json
                        def _flatten(deps, collect):
                            for dep in deps:
                                collect.append({'package': dep['name'], 'version': dep['version']})
                                _flatten(dep['dependencies'], collect)
                        resolved_deps = []
                        _flatten(manifest_dependencies, resolved_deps)
                    else:  # pom.xml, requirements.txt
                        resolved_deps =\
                            [{'package': x.split(' ')[0], 'version': x.split(' ')[1]}
                             for x in manifest_dependencies]
                else:  # package.json
                    resolved_deps = self._handle_external_deps(
                        self.storage.get_ecosystem(arguments['ecosystem']),
                        out["details"][0]["dependencies"])
                out["details"][0]['_resolved'] = resolved_deps
            result.append(out)

        return {'result': result, 'user_profile': user_profile}

