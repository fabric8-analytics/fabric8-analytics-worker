"""Collects statistics using Github API."""

from urllib.parse import urljoin

import datetime

from f8a_worker.base import BaseTask
from f8a_worker.errors import NotABugTaskError
from f8a_worker.utils import (parse_gh_repo,
                              get_response,
                              get_gh_contributors,
                              store_data_to_s3,
                              get_gh_pr_issue_counts)
from f8a_utils.golang_utils import GolangUtils
from selinon import StoragePool
import logging

logger = logging.getLogger(__name__)
REPO_PROPS = ('forks_count', 'subscribers_count', 'stargazers_count', 'open_issues_count')


class NewGithubTask(BaseTask):
    """Collects statistics using Github API."""

    # used for testing
    _repo_name = None
    _repo_url = None

    @classmethod
    def create_test_instance(cls, repo_name, repo_url):
        """Create instance of task for tests."""
        assert cls
        instance = super().create_test_instance()
        # set for testing
        instance._repo_name = repo_name
        instance._repo_url = repo_url
        return instance

    def _get_last_years_commits(self, repo_url):
        """Get weekly commit activity for last year."""
        try:
            activity = get_response(urljoin(repo_url + '/', "stats/commit_activity"))
        except NotABugTaskError as e:
            logger.debug(e)
            return []
        return [x['total'] for x in activity]

    def _get_repo_stats(self, repo):
        """Collect various repository properties."""
        try:
            url = repo.get('contributors_url', '')
            if url:
                contributors = get_gh_contributors(url)
            else:
                contributors = -1
        except NotABugTaskError as e:
            logger.error(e)
            contributors = -1
        d = {'contributors_count': contributors}
        for prop in REPO_PROPS:
            d[prop] = repo.get(prop, -1)
        return d

    def _get_repo_name(self, url):
        """Get GitHub repo URL."""
        parsed = parse_gh_repo(url)
        if not parsed:
            logger.debug('Could not parse Github repo URL %s', url)
        else:
            self._repo_url = 'https://github.com/' + parsed
        return parsed

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        result_data = {'status': 'unknown',
                       'summary': [],
                       'details': {}}

        if arguments['ecosystem'] == 'golang':
            go_obj = GolangUtils(arguments.get('name'))
            url = go_obj.get_gh_link()

            if url:
                arguments['url'] = url
            else:
                return result_data

        # For testing purposes, a repo may be specified at task creation time
        if self._repo_name is None:
            # Otherwise, get the repo name from URL
            self._repo_name = self._get_repo_name(arguments['url'])
            if self._repo_name is None:
                # Not a GitHub hosted project
                return result_data

        repo_url = urljoin(self.configuration.GITHUB_API + "repos/", self._repo_name)
        repo = {}
        try:
            repo = get_response(repo_url)
        except NotABugTaskError as e:
            logger.error(e)

        result_data['status'] = 'success'

        issues = {}
        # Get Repo Statistics
        notoriety = self._get_repo_stats(repo)

        if notoriety:
            issues.update(notoriety)
        issues['topics'] = repo.get('topics', [])
        issues['license'] = repo.get('license') or {}

        # Get Commit Statistics
        last_year_commits = self._get_last_years_commits(repo.get('url', ''))
        commits = {'last_year_commits': {'sum': sum(last_year_commits),
                                         'weekly': last_year_commits}}

        t_stamp = datetime.datetime.utcnow()
        refreshed_on = {'updated_on': t_stamp.strftime("%Y-%m-%d %H:%M:%S")}
        issues.update(refreshed_on)
        issues.update(commits)

        # Get PR/Issue details for previous Month and Year
        gh_pr_issue_details = get_gh_pr_issue_counts(self._repo_name)

        issues.update(gh_pr_issue_details)
        result_data['details'] = issues

        # Store github details for being used in Data-Importer
        store_data_to_s3(arguments,
                         StoragePool.get_connected_storage('S3GitHub'),
                         result_data)

        return result_data
