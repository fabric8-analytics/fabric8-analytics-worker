"""Computes various Issues and PRS for Golang Packages repositories.

output: cve format containing PR,Issues for the a golang package/repositories
sample output:
{'status': 'success','package': '','summary': [],'details': {}}
"""

from f8a_worker.base import BaseTask
from f8a_worker.errors import F8AConfigurationException, NotABugTaskError, NotABugFatalTaskError
from selinon import FatalTaskError
import requests
from requests import HTTPError
import urllib
import time


class GoCVEpredictorTask(BaseTask):
    """Computes various Issues and PRS for Golang Packages/repositories."""

    _analysis_name = 'GoCVEpredictorTask'
    GITHUB_API_URL = 'https://api.github.com/repos/'
    GITHUB_URL = 'https://github.com/'
    GITHUB_TOKEN = ''

    def get_response_issues(self, url, headers=None, sleep_time=2, retry_count=10):
        """Wrap requests which tries to get response.

        :param url: URL where to do the request
        :param headers: additional headers for request
        :param sleep_time: sleep time between retries
        :param retry_count: number of retries
        :return: content of response's json
        """
        try:
            for _ in range(retry_count):
                response = requests.get(url, headers=headers, params={'access_token': self.GITHUB_TOKEN})
                response.raise_for_status()
                if response.status_code == 204:
                    # json() below would otherwise fail with JSONDecodeError
                    raise HTTPError('No content')
                response = response.json()
                if response:
                    return response
                time.sleep(sleep_time)
            else:
                raise NotABugTaskError("Number of retries exceeded")
        except HTTPError as err:
            message = "Failed to get results from {url} with {err}".format(url=url, err=err)
            raise NotABugTaskError(message) from err

    def _processJSonIssuePR(self, result, repository, event, package):

        comments = ""
        finalData = {}
        finalData['package'] = package
        finalData['githublink'] = self.GITHUB_URL + repository
        finalData['number'] = result['number']

        # Fetching Comments section
        comments_Json = self.get_response_issues(result['comments_url'])
        for entry in comments_Json:
            comments = comments + '\n' + entry['body']

        description = result['title'] + '\n' + result['body'] + comments
        finalData[event] = description
        return finalData

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results

        """
        result_data = {'status': 'unknown',
                       'package': '',
                       'summary': [],
                       'details': {}}
        # self._strict_assert(arguments.get('package'))
        # self._strict_assert(arguments.get('repository'))
        # self._strict_assert(arguments.get('event'))
        # self._strict_assert(arguments.get('number'))
        event = ''
        package = arguments.get('package')
        repository = arguments.get('repository')
        if arguments.get('event'):
            event = arguments.get('event').split('-')[0]
        isprnumber = arguments.get('number')

        # For testing purposes
        if package is None:
            return result_data

        try:
            token, header = self.configuration.select_random_github_token()
            self.GITHUB_TOKEN = token
        except F8AConfigurationException as e:
            self.log.error(e)
            raise FatalTaskError from e
            return result_data
        except Exception as e:
            self.log.error(e)
            raise FatalTaskError from e
            return result_data

        # Generating Request URL to fetch Data
        url_path = repository + '/' + event + 's/' + isprnumber
        url_template = urllib.parse.urljoin(self.GITHUB_API_URL, url_path)
        print(url_template.format())

        # Call the GitHub APIs to get the data
        try:
            result = self.get_response_issues(url_template.format())
        except NotABugTaskError as e:
            self.log.error(e)
            raise NotABugFatalTaskError from e

        # Process the received data
        result_data['status'] = 'success'
        result_data['package'] = package
        finalData = self._processJSonIssuePR(result, repository, event,
                                             package)
        result_data['details'] = finalData
        return result_data
