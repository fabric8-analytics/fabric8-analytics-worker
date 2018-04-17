"""Class to notify gemini analytics scan report."""

import os
import requests as req

from f8a_worker.base import BaseTask


class GeminiNotifierTask(BaseTask):
    """Initialize Analysis."""

    @staticmethod
    def generate_report(data):
        """Generate report based on a template."""
        content = 'Scan Report\n' \
                  '=====================================\n' \
                  '### GIT URL: {git_url}\n' \
                  '### GIT Commit Hash: {git_sha}\n' \
                  '### Report Generated at: {scanned_at} UTC\n' \
                  '### Dependencies scanned: {dependencies}\n' \
                  '\n' \
                  ''.format(git_url=data.get('git_url'),
                            git_sha=data.get('git_sha'),
                            scanned_at=data.get('scanned_at'),
                            dependencies=data.get('dependencies'))

        dependency_data = list()
        for dependency in data.get('dependencies'):
            if dependency.get('cves'):
                dependency_data.append('Security vulnerability '
                                       '{cve} found with the highest CVSS score {score} '
                                       'for application dependency {name}:{ver}'
                                       .format(content=content, name=dependency.get('name'),
                                               ver=dependency.get('version'),
                                               cve=dependency.get('cve_id_for_highest_cvss_score'),
                                               score=dependency.get('highest_cvss_score')))

        data = '\n'.join(dependency_data)
        content = '{}\n{}'.format(content, data)
        return content

    def create_github_issue(self, url, title, report):
        """Create a GitHub issue with the generated report."""
        payload = {
            "title": title,
            "body": report
        }
        try:
            header = {'Authorization': 'token {}'.format(os.getenv('GITHUB_TOKEN', ''))}
            resp = req.post(url, json=payload, headers=header)
            if resp.status_code == 201:
                self.log.info("GitHub issue creation request accepted")
            # 410 - Gone
            else:
                self.log.exception(resp.content)
        except Exception as e:
            self.log.exception("Exception: {}".format(e))

    def execute(self, arguments=None):
        """Gemini report notification task."""
        arguments = self.parent_task_result("ReportGenerationTask")
        self._strict_assert(arguments)
        report = GeminiNotifierTask.generate_report(arguments)
        url = arguments.get('git_url').split('/')[-2:]
        api_url = 'https://api.github.com/repos/{}/{}/issues'.format(url[0], url[1])
        title = 'Anomaly scan failure at {}'.format(arguments.get('scanned_at'))
        self.create_github_issue(api_url, title, report)
