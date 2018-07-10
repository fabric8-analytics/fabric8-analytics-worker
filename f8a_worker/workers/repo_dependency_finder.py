"""Output: List of direct and indirect dependencies."""

import requests
import traceback

from f8a_worker.base import BaseTask
from f8a_worker.errors import TaskError
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.workers.mercator import MercatorTask
from f8a_worker.workers.dependency_parser import GithubDependencyTreeTask


class RepoDependencyFinderTask(BaseTask):
    """Finds out direct and indirect dependencies from a given github repository."""

    _mercator = MercatorTask.create_test_instance(task_name='RepoDependencyFinderTask')

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from flow: {}".format(arguments))
        self._strict_assert(arguments.get('service_token'))

        github_repo = arguments.get('github_repo')
        dependencies = []
        repo_cves = []

        if len(arguments.get('epv_list', [])):
            for epv in arguments.get('epv_list'):
                dependencies.append('{ecosystem}:{package}:{version}'
                                    .format(ecosystem=epv.get('ecosystem'),
                                            package=epv.get('name'),
                                            version=epv.get('version')))
            self.logger.debug('Dependencies list: %r' % dependencies)
            try:
                repo_cves = self.get_cve(dependencies)
            except TaskError as e:
                raise TaskError('Failed to get CVEs')
        else:
            dependencies = list(GithubDependencyTreeTask.extract_dependencies(github_repo))
            self.log.debug('Retrieved dependencies list %r' % dependencies)
            try:
                # forward only the available dependencies in the system. Unknown
                # dependencies are not going to be ingested for osioUserNotificationFlow.
                repo_cves = self.create_repo_node_and_get_cve(github_repo, dependencies)
                self.log.info('Identified CVEs %r' % repo_cves)
            except TaskError as e:
                raise TaskError('Failed to Create Repo Node')

        report = self.generate_report(repo_cves=repo_cves, deps_list=dependencies)
        return {'report': report, 'service_token': arguments['service_token']}

    def create_repo_node_and_get_cve(self, github_repo, deps_list):
        """Create a repository node in the graphdb and create its edges to all deps.

        :param github_repo:
        :param dependencies:
        :return: {}, gremlin_response
        """
        gremlin_str = "repo=g.V().has('repo_url', '{repo_url}').tryNext().orElseGet{{" \
                      "graph.addVertex('vertex_label', 'Repo', 'repo_url', '{repo_url}')}};" \
                      "g.V(repo).outE('has_dependency').drop().iterate();".format(
                          repo_url=github_repo)

        for pkg in deps_list:
            ecosystem = pkg.split(':')[0]
            version = pkg.split(':')[-1]
            name = pkg.replace(ecosystem + ':', '').replace(':' + version, '')
            gremlin_str += "ver=g.V().has('pecosystem', '{ecosystem}').has('pname', '{name}')." \
                           "has('version', '{version}');ver.hasNext() && " \
                           "g.V(repo).next().addEdge('has_dependency', ver.next());".format(
                               ecosystem=ecosystem, name=name, version=version)

        # Traverse the Repo to EPVs that have CVE's and report them
        gremlin_str += "g.V(repo).as('rp').out('has_dependency').has('cve_ids').as('epv')" \
                       ".select('rp','epv').by(valueMap());"
        payload = {"gremlin": gremlin_str}
        try:
            rawresp = requests.post(url=GREMLIN_SERVER_URL_REST, json=payload)
            resp = rawresp.json()
            self.log.debug('Gremlin Response %r' % resp)
            if rawresp.status_code != 200:
                raise TaskError("Error creating repository node for {repo_url} - "
                                "{resp}".format(repo_url=github_repo, resp=resp))
        except Exception:
            self.log.error(traceback.format_exc())
            raise TaskError(
                "Error creating repository node for {repo_url}".format(repo_url=github_repo))
            return None

        return resp

    def get_cve(self, deps_list):
        """
        Get CVE information for dependencies from the Graph database.

        :param deps_list:
        :return: gremlin_response
        """
        package_set = set()
        version_set = set()
        eco_set = set()
        for epv in deps_list:
            ecosystem = epv.split(':')[0]
            eco_set.add(ecosystem)
            version = epv.split(':')[-1]
            version_set.add(version)
            name = epv.replace(ecosystem + ':', '').replace(':' + version, '')
            package_set.add(name)

        gremlin_str = "g.V().has('pecosystem', within(eco_list)).has('pname', within(pkg_list))." \
                      "has('version', within(ver_list)).in('has_dependency').dedup().as('rp')." \
                      "out('has_dependency').has('cve_ids').as('epv').select('rp','epv')." \
                      "by(valueMap());"
        payload = {
            'gremlin': gremlin_str,
            'bindings': {
                'eco_list': list(eco_set),
                'pkg_list': list(package_set),
                'ver_list': list(version_set)
            }
        }
        try:
            rawresp = requests.post(url=GREMLIN_SERVER_URL_REST, json=payload)
            resp = rawresp.json()
            if rawresp.status_code != 200:
                raise RuntimeError("Error creating repository node for %r" % resp)
        except Exception:
            self.log.error(traceback.format_exc())
            raise RuntimeError("Error creating repository node")
            return None

        return resp

    def generate_report(self, repo_cves, deps_list):
        """
        Generate a json structure to include cve details for dependencies.

        :param repo_cves:
        :param deps_list:
        :return: list
        """
        repo_list = []
        for repo_cve in repo_cves.get('result').get('data', []):
            epv = repo_cve.get('epv')
            repo_url = repo_cve.get('rp').get('repo_url')[0]
            name = epv.get('pname')[0]
            version = epv.get('version')[0]
            ecosystem = epv.get('pecosystem')[0]
            str_epv = ecosystem + ":" + name + ":" + version
            cve_count = len(epv.get('cve_ids', []))
            vulnerable_deps = []
            first = True
            if cve_count > 0 and str_epv in deps_list:
                cve_list = []
                for cve in epv.get('cve_ids'):
                    cve_id = cve.split(':')[0]
                    cvss = cve.split(':')[-1]
                    cve_list.append({'CVE': cve_id, 'CVSS': cvss})
                vulnerable_deps.append(
                    {'ecosystem': epv.get('pecosystem')[0], 'name': epv.get('pname')[0],
                        'version': epv.get('version')[0], 'cve_count': cve_count, 'cves': cve_list})

            for repo in repo_list:
                if repo_url == repo.get('repo_url'):
                    repo_vul_deps = repo.get('vulnerable_deps')
                    repo['vulnerable_deps'] = vulnerable_deps + repo_vul_deps
                    first = False
            if first:
                repo_list.append({'repo_url': repo_url, 'vulnerable_deps': vulnerable_deps})

        return repo_list
