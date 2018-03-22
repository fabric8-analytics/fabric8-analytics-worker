"""Output: TBD."""

from f8a_worker.base import BaseTask
import requests
from f8a_worker.defaults import configuration


class GithubIssueCreator(BaseTask):
    """Creates a GH issue with scan results."""

    def execute(self, arguments=None):
        report_generation_result = self.parent_task_result("ReportGenerationTask")
        self.log.info("Result obtained from ReportGenerationTask: {}".format(report_generation_result))
        self._strict_assert(report_generation_result.get("dependencies"))
        self._strict_assert(report_generation_result.get("git_url"))
        self._strict_assert(report_generation_result.get("git_sha"))
        self._strict_assert(report_generation_result.get("scanned_at"))

        report = GithubIssueCreator.generate_report(report_generation_result)
        url = report_generation_result.get("git_url").split("/")[-2:]
        api_url = "https://api.github.com/repos/{}/{}/issues".format(url[0], url[1])
        self.log.info("Creating GH Issue at following url: {}".format(api_url))
        issue_title = "Anomaly scan failure at {}".format(report_generation_result.get("scanned_at"))
        issue_content = self.create_github_issue(api_url, issue_title, report).get("issue_content")
        return {"result": issue_content}

    @staticmethod
    def generate_report(data):
        content = 'Scan Report\n' \
                  '=====================================\n' \
                  '### GIT URL: {git_url}\n' \
                  '### GIT Commit Hash: {git_sha}\n' \
                  '### Report Generated at: {scanned_at} UTC\n' \
                  '\n' \
                  ''.format(git_url=data.get('git_url'),
                            git_sha=data.get('git_sha'),
                            scanned_at=data.get('scanned_at'))
        dep_data = []
        for dep in data['dependencies']:
            if dep.get('cves'):
                dep_data.append('Security vulnerability '
                                '{cve} found with the highest CVSS score {score} '
                                'for application dependency {name}:{ver}'.
                                format(content=content, name=dep.get('name'),
                                       ver=dep.get('version'), cve=dep.get('cve_id_for_highest_cvss_score'),
                                       score=dep.get('highest_cvss_score')))

        data = '\n'.join(dep_data)
        content = '{}\n{}'.format(content, data)
        return content

    def create_github_issue(self, url, title, report):
        payload = {
            "title": title,
            "body": report
        }
        result = {
            "issue_content": None
        }
        self.log.info("Payload sent to GH is: {}".format(payload))
        try:
            header = {'Authorization': 'token {}'.format(configuration.GITHUB_TOKEN)}
            resp = requests.post(url, json=payload, headers=header)
            if resp.status_code == 201:
                self.log.debug("Request accepted and issue created for repo: {}".format(url))
                result["issue_content"] = resp.content
                return result
            else:
                self.log.debug("Something went wrong while creating issue for repo: {}".format(url))
                self.log.debug(resp.content)
                result["issue_content"] = resp.content
                return result

        except Exception as e:
            self.log.debug("Exception: {}".format(e))
            return result
