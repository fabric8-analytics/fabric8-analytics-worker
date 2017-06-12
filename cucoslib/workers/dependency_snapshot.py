import datetime
from re import compile as regexp
import urllib.parse

from cucoslib.base import BaseTask
from cucoslib.enums import EcosystemBackend
from cucoslib.errors import TaskError
from cucoslib.schemas import SchemaRef
from cucoslib.solver import get_ecosystem_solver
from cucoslib.utils import json_serial

gh_dep = regexp('@?[\w-]+/[\w-]+')


class DependencySnapshotTask(BaseTask):
    _analysis_name = 'dependency_snapshot'
    description = 'Task that analyzes dependencies'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def _collect_dependencies(self):
        """
        Return all dependencies for current analysis flow (operates on parent mercator result)

        :return: List[str], list of dependencies
        """
        wr = self.parent_task_result('metadata')
        if not isinstance(wr, dict):
            raise TaskError('metadata task result has unexpected type: {}; expected dict'.
                            format(type(wr)))

        # there can be details about multiple manifests in the metadata, therefore we will collect dependency
        # specifications from all of them and exclude obvious duplicates along the way
        dependencies = list({dep for m in wr.get('details', []) if m.get('dependencies')
                             for dep in m.get('dependencies', [])})
        return dependencies

    def _resolve_dependency(self, ecosystem, dep):
        ret = {'ecosystem': ecosystem.name,
               'declaration': dep,
               'resolved_at': json_serial(datetime.datetime.now())}

        # first, if this is a Github dependency, return it right away (we don't resolve these yet)
        if ' ' in dep:
            # we have both package name and version (version can be an URL)
            name, spec = dep.split(' ', 1)
            if gh_dep.match(spec):
                ret['name'] = name
                ret['version'] = 'https://github.com/' + spec
            elif urllib.parse.urlparse(spec).scheme is not '':
                ret['name'] = name
                ret['version'] = spec
        else:
            if gh_dep.match(dep):
                ret['name'] = 'https://github.com/' + dep
                ret['version'] = None
            elif urllib.parse.urlparse(dep).scheme is not '':
                ret['name'] = dep
                ret['version'] = None

        if 'name' in ret:
            return ret

        # second, figure out what is the latest upstream version matching the spec and return it
        solver = get_ecosystem_solver(ecosystem)
        pkgspec = solver.solve([dep])

        if not pkgspec:
            raise TaskError("invalid dependency: {}".format(dep))

        package, version = pkgspec.popitem()
        if not version:
            raise TaskError("bad version resolved for {}".format(dep))

        ret['name'] = package
        ret['version'] = version
        return ret

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))

        result = {'summary': {'errors': [], 'dependency_counts': {}},
                  'status': 'success', 'details': {}}
        ecosystem = self.storage.get_ecosystem(arguments.get('ecosystem'))
        try:
            deps = self._collect_dependencies()
        except TaskError as e:
            self.log.error(str(e))
            result['summary']['errors'].append(str(e))
            result['status'] = 'error'
            return result

        resolved_deps = []
        for dep in deps:
            try:
                resolved = self._resolve_dependency(ecosystem, dep)
            except TaskError as e:
                self.log.error(str(e))
                result['summary']['errors'].append(str(e))
                result['status'] = 'error'
            self.log.info('resolved dependency %s as %s', resolved, dep)
            resolved_deps.append(resolved)
        # in future, we may want to provide also build/test dependencies, not just runtime
        result['details']['runtime'] = resolved_deps
        result['summary']['dependency_counts']['runtime'] = len(resolved_deps)
        return result
