"""Collects statistics using Github API."""

from urllib.parse import urljoin

import requests
import datetime
from collections import OrderedDict

from f8a_worker.base import BaseTask
from f8a_worker.errors import (NotABugTaskError,
                               NotABugFatalTaskError)
from f8a_worker.utils import (parse_gh_repo,
                              get_response,
                              get_gh_contributors,
                              get_gh_pr_issue_counts)
import logging

logger = logging.getLogger(__name__)

REPO_PROPS = ('forks_count', 'subscribers_count', 'stargazers_count', 'open_issues_count')


class GithubTask(BaseTask):
    """Collects statistics using Github API."""

    # used for testing
    _repo_name = None
    _repo_url = None

    @classmethod
    def create_test_instance(cls, repo_name, repo_url):
        """Create instance of task for tests."""
        assert cls
        instance = super().create_test_instance()
        # set for testing as we are not querying DB for mercator results
        instance._repo_name = repo_name
        instance._repo_url = repo_url
        return instance

    def _get_last_years_commits(self, repo_url):
        """Get weekly commit activity for last year."""
        try:
            activity = get_response(urljoin(repo_url + '/', "stats/commit_activity"))
            if activity is None:
                return []
            return [x.get('total', 0) for x in activity]
        except NotABugTaskError as e:
            self.log.debug(e)
            return []

    def _get_repo_stats(self, repo):
        """Collect various repository properties."""
        try:
            url = repo.get('contributors_url', '')
            if url:
                contributors = get_gh_contributors(url)
            else:
                contributors = -1
        except NotABugTaskError as e:
            self.log.debug(e)
            contributors = -1
        d = {'contributors_count': contributors}
        for prop in REPO_PROPS:
            d[prop] = repo.get(prop, -1)
        return d

    def _get_repo_name(self, url):
        """Retrieve GitHub repo from a preceding Mercator scan."""
        parsed = parse_gh_repo(url)
        if not parsed:
            self.log.debug('Could not parse Github repo URL %s', url)
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
        # For testing purposes, a repo may be specified at task creation time
        if self._repo_name is None:
            # Otherwise, get the repo name from earlier Mercator scan results
            self._repo_name = self._get_repo_name(arguments['url'])
            if self._repo_name is None:
                # Not a GitHub hosted project
                return result_data

        repo_url = urljoin(self.configuration.GITHUB_API + "repos/", self._repo_name)
        try:
            repo = get_response(repo_url)
            if not repo:
                raise NotABugFatalTaskError('Page not found on {}'.format(repo_url))
        except NotABugTaskError as e:
            self.log.error(e)
            raise NotABugFatalTaskError from e

        result_data['status'] = 'success'

        issues = {}
        # Get Repo Statistics
        notoriety = self._get_repo_stats(repo)

        if notoriety:
            issues.update(notoriety)
        issues['topics'] = repo.get('topics', [])
        issues['license'] = repo.get('license') or {}

        # Get Commit Statistics
        last_year_commits = self._get_last_years_commits(repo['url'])
        commits = {'last_year_commits': {'sum': sum(last_year_commits),
                                         'weekly': last_year_commits}}
        t_stamp = datetime.datetime.utcnow()
        refreshed_on = {'updated_on': t_stamp.strftime("%Y-%m-%d %H:%M:%S")}
        issues.update(refreshed_on)
        issues.update(commits)

        # Get PR/Issue details for previous Month and Year
        gh_pr_issue_details = get_gh_pr_issue_counts(repo['full_name'])
        issues.update(gh_pr_issue_details)

        result_data['details'] = issues
        return result_data


class GitReadmeCollectorTask(BaseTask):
    """Collect README files stored on Github."""

    _GITHUB_README_PATH = \
        'https://raw.githubusercontent.com/{project}/{repo}/master/README{extension}'

    # Based on https://github.com/github/markup#markups
    # Markup type to its possible extensions mapping, we use OrderedDict as we
    # check the most used types first
    README_TYPES = OrderedDict((
        ('Markdown', ('md', 'markdown', 'mdown', 'mkdn')),
        ('reStructuredText', ('rst',)),
        ('AsciiDoc', ('asciidoc', 'adoc', 'asc')),
        ('Textile', ('textile',)),
        ('RDoc', ('rdoc',)),
        ('Org', ('org',)),
        ('Creole', ('creole',)),
        ('MediaWiki', ('mediawiki', 'wiki')),
        ('Pod', ('pod',)),
        ('Unknown', ('',)),
    ))

    def _get_github_readme(self, url):
        """Get README from url."""
        repo_tuple = parse_gh_repo(url)
        if repo_tuple:
            project, repo = repo_tuple.split('/')
        else:
            return None

        for readme_type, extensions in self.README_TYPES.items():
            for extension in extensions:
                if extension:
                    extension = '.' + extension
                url = self._GITHUB_README_PATH.format(project=project, repo=repo,
                                                      extension=extension)
                response = requests.get(url)
                if response.status_code != 200:
                    self.log.debug('No README%s found for type "%s" at "%s"', extension,
                                   readme_type, url)
                    continue

                self.log.debug('README%s found for type "%s" at "%s"', extension, readme_type, url)
                return {'type': readme_type, 'content': response.text}

    def run(self, arguments):
        """Task's entrypoint."""
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('url'))

        readme = self._get_github_readme(arguments['url'])
        if not readme:
            self.log.warning("No README file found for '%s/%s'", arguments['ecosystem'],
                             arguments['name'])

        return readme
