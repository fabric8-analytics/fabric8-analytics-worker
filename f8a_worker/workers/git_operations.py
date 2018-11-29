"""Git Operations Task."""

import json
from f8a_worker.base import BaseTask
from git import Repo
from werkzeug.datastructures import FileStorage
import os
from requests_futures.sessions import FuturesSession

_dir_path = "/tmp/clonedRepos"
worker_count = int(os.getenv('FUTURES_SESSION_WORKER_COUNT', '100'))
_session = FuturesSession(max_workers=worker_count)

F8_API_BACKBONE_HOST = os.getenv('F8_API_BACKBONE_HOST', 'http://f8a-server-backbone:5000')
GEMINI_SERVER_URL = os.getenv('F8A_GEMINI_SERVER_SERVICE_HOST', 'http://f8a-gemini-server:5000')


class GitOperationTask(BaseTask):
    """Do the git operations to get manifest files."""

    @staticmethod
    def generate_files_for_maven(path, manifests):
        """Generate files for maven ecosystem."""
        os.system("cd " + path + "; mvn install; "
                  "mvn org.apache.maven.plugins:maven-dependency-plugin:3.1.1:collect"
                  " -DoutputFile=direct-dependencies.txt "
                  "-DincludeScope=runtime "
                  "-DexcludeTransitive=true; "
                  "mvn org.apache.maven.plugins:maven-dependency-plugin:3.1.1:collect"
                  " -DoutputFile=transitive-dependencies.txt "
                  "-DincludeScope=runtime "
                  "-DexcludeTransitive=false")
        manifests.append(FileStorage
                         (open(path + "/direct-dependencies.txt", 'rb'),
                          filename='direct-dependencies.txt'))
        manifests.append(FileStorage
                         (open(path + "/transitive-dependencies.txt", 'rb'),
                          filename='transitive-dependencies.txt'))
        return manifests

    @staticmethod
    def generate_files_for_node(path, manifests):
        """Generate files for npm ecosystem."""
        os.system("cd " + path + "; npm install")
        os.system("cd " + path + "; npm list --prod --json > npmlist.json")
        manifests.append(FileStorage(open(path + "/npmlist.json", 'rb'),
                                     filename='npmlist.json'))
        return manifests

    def create_repo_and_generate_files(self,
                                       giturl,
                                       ecosystem,
                                       gh_token):
        """Create a repo and generate dep files."""
        repo_name = giturl.split("/")[-1]
        path = _dir_path + "/" + repo_name
        token = gh_token.get('access_token')
        os.system("rm -rf " + path)
        manifests = []
        try:
            url = "https://" + token + ":x-oauth-basic@" + giturl.split("//")[1]
            Repo.clone_from(url, path)

            if ecosystem == "maven":
                manifests = GitOperationTask.generate_files_for_maven(
                    path, manifests
                )
            elif ecosystem == "npm":
                manifests = GitOperationTask.generate_files_for_node(
                    path, manifests
                )
        except Exception:
            self.log.exception("Exception while cloning repo or generating files.")

        return manifests

    def gemini_call_for_cve_scan(self, scan_repo_url, ecosystem, manifests, auth_key):
        """Do the delegate call to gemini."""
        try:
            api_url = GEMINI_SERVER_URL
            data = {'git-url': scan_repo_url,
                    'ecosystem': ecosystem}
            deps = []
            for file in manifests:
                deps.append((
                    'dependencyFile[]', (
                        file['filename'],
                        file['content'],
                        'text/plain'
                    )
                ))
            _session.headers['Authorization'] = auth_key
            resp = _session.post('{}/api/v1/user-repo/scan'.format(api_url),
                                 data=data, files=deps)
            self.log.info(resp.result().content)
        except Exception:
            self.log.exception("Failed to call the gemini scan.")

    def backbone_for_stack_analysis(self, deps, request_id, is_modified_flag, check_license):
        """Do the delegate call to gemini."""
        deps['external_request_id'] = request_id
        deps.update(is_modified_flag)
        self.log.info("Calling aggregator and recommender")
        self.log.info(deps)
        try:
            api_url = F8_API_BACKBONE_HOST
            _session.post(
                '{}/api/v1/stack_aggregator'.format(api_url), json=deps,
                params={'check_license': str(check_license).lower()})
            _session.post('{}/api/v1/recommender'.format(api_url), json=deps,
                          params={'check_license': str(check_license).lower()})
        except Exception:
            self.log.exception("Failed to call the gemini scan.")

    def execute(self, arguments):
        """Perform the git operations."""
        self.log.info("Worker flow initiated for git operations")
        self._strict_assert(arguments.get('git_url'))
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('is_scan_enabled'))
        self._strict_assert(arguments.get('request_id'))
        self._strict_assert(arguments.get('gh_token'))

        giturl = arguments.get('git_url')
        ecosystem = arguments.get('ecosystem')
        request_id = arguments.get('request_id')
        is_modified_flag = arguments.get('is_modified_flag')
        check_license = arguments.get('check_license')
        auth_key = arguments.get('auth_key')
        gh_token = arguments.get('gh_token')
        is_scan_enabled = arguments.get('is_scan_enabled')

        manifests = self.create_repo_and_generate_files(giturl,
                                                        ecosystem,
                                                        gh_token)
        if len(manifests) == 0:
            self.log.error("No dependency files found or generated.")
            return None

        data_object = []
        for manifest in manifests:
            temp = {
                'filename': manifest.filename,
                'content': manifest.read()
            }
            data_object.append(temp)

        repo_name = giturl.split("/")[-1]
        path = _dir_path + "/" + repo_name

        # Call to the Gemini Server
        if is_scan_enabled == "true":
            self.log.info("Scan is enabled.Gemini scan call in progress")
            try:
                self.gemini_call_for_cve_scan(giturl,
                                              ecosystem,
                                              data_object,
                                              auth_key)
            except Exception:
                self.log.exception("Failed to call the gemini scan.")

        # Call to the Backbone
        deps = DependencyFinder.scan_and_find_dependencies(path, ecosystem, data_object)
        self.log.debug(deps)
        if len(deps) == 0:
            self.log.error("Dependencies not generated properly.Backbone wont be called.")
            return None

        try:
            self.log.info("Calling backbone for stack analyses")
            self.backbone_for_stack_analysis(deps,
                                             request_id,
                                             is_modified_flag,
                                             check_license)

        except Exception:
            self.log.exception("Failed to call the backbone.")
        os.system("rm -rf " + path)


class DependencyFinder:
    """Implementation of methods to find dependencies from manifest file."""

    def __init__(self):
        """Init function."""
        return None

    @staticmethod
    def scan_and_find_dependencies(path, ecosystem, manifests):
        """Scan the dependencies files to fetch transitive deps."""
        deps = dict()
        if ecosystem == "npm":
            deps = DependencyFinder.get_npm_dependencies(path,
                                                         ecosystem,
                                                         manifests)
        return deps

    @staticmethod
    def get_npm_dependencies(path, ecosystem, manifests):
        """Scan the npm dependencies files to fetch transitive deps."""
        deps = {}
        result = []
        details = []
        for manifest in manifests:
            dep = {
                "ecosystem": ecosystem,
                "manifest_file_path": path,
                "manifest_file": manifest['filename']
            }

            dependencies = json.loads(manifest['content'].decode('utf-8')).get('dependencies')
            resolved = []
            if dependencies:
                for key, val in dependencies.items():
                    version = val.get('version') or val.get('required').get('version')
                    if version:
                        transitive = []
                        tr_deps = val.get('dependencies') or \
                            val.get('required', {}).get('dependencies')
                        if tr_deps:
                            transitive = DependencyFinder.get_npm_transitives(transitive, tr_deps)
                        tmp_json = {
                            "package": key,
                            "version": version,
                            "deps": transitive
                        }
                        resolved.append(tmp_json)
            dep['_resolved'] = resolved
            details.append(dep)
            details_json = {"details": details}
            result.append(details_json)
        deps['result'] = result
        return deps

    @staticmethod
    def get_npm_transitives(transitive, content):
        """Scan the npm dependencies recursively to fetch transitive deps."""
        if content:
            for key, val in content.items():
                version = val.get('version') or val.get('required').get('version')
                if version:
                    tmp_json = {
                        "package": key,
                        "version": version
                    }
                    transitive.append(tmp_json)
                    tr_deps = val.get('dependencies') or val.get('required', {}).get('dependencies')
                    if tr_deps:
                        transitive = DependencyFinder.get_npm_transitives(transitive, tr_deps)
        return transitive
