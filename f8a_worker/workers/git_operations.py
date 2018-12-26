"""Git Operations Task."""

import json
from f8a_worker.base import BaseTask
from git import Repo
from werkzeug.datastructures import FileStorage
from f8a_utils.dependency_finder import DependencyFinder
import os
from requests_futures.sessions import FuturesSession

_dir_path = "/tmp/clonedRepos"
worker_count = int(os.getenv('FUTURES_SESSION_WORKER_COUNT', '100'))
_session = FuturesSession(max_workers=worker_count)

F8_API_BACKBONE_HOST = os.getenv('F8_API_BACKBONE_HOST', 'http://f8a-server-backbone:5000')
GEMINI_SERVER_URL = os.getenv('F8A_GEMINI_SERVER_SERVICE_HOST', 'http://f8a-gemini-server:5000')
AUTH_KEY = os.getenv('OS_AUTH_KEY', '')


class GitOperationTask(BaseTask):
    """Do the git operations to get manifest files."""

    @staticmethod
    def generate_files_for_maven(path, manifests):
        """Generate files for maven ecosystem."""
        os.system("cd " + path + "; "
                  "mvn org.apache.maven.plugins:maven-dependency-plugin:3.0.2:tree"
                  " -DoutputFile=" + path + "/tmp/dependencies.txt "
                  "-DoutputType=dot "
                  "-DappendOutput=true; ")
        manifests.append(FileStorage
                         (open(path + "/tmp/dependencies.txt", 'rb'),
                          filename='dependencies.txt'))
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
        token = gh_token.get('access_token') or ""
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

    def gemini_call_for_cve_scan(self, scan_repo_url, deps, auth_key):
        """Do the delegate call to gemini."""
        try:
            api_url = GEMINI_SERVER_URL
            _session.headers['Authorization'] = AUTH_KEY or auth_key
            _session.headers['git-url'] = scan_repo_url
            _session.headers['Content-Type'] = "application/json"
            resp = _session.post('{}/api/v1/user-repo/scan'.format(api_url),
                                 data=json.dumps(deps))
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
            self.log.exception("Failed to call backbone.")

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
        repo_name = giturl.split("/")[-1]
        path = _dir_path + "/" + repo_name
        data_object = []
        for manifest in manifests:
            temp = {
                'filename': manifest.filename,
                'content': manifest.read(),
                'filepath': path
            }
            data_object.append(temp)

        deps = DependencyFinder.scan_and_find_dependencies(ecosystem, data_object)
        # Call to the Gemini Server
        if is_scan_enabled == "true":
            self.log.info("Scan is enabled.Gemini scan call in progress")
            try:
                self.gemini_call_for_cve_scan(giturl,
                                              deps,
                                              auth_key)
            except Exception:
                self.log.exception("Failed to call the gemini scan.")

        # Call to the Backbone
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
