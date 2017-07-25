from bs4 import BeautifulSoup
import requests
import github
import random
import time
from collections import OrderedDict

from f8a_worker.schemas import SchemaRef
from f8a_worker.base import BaseTask
from f8a_worker.utils import parse_gh_repo

REPO_PROPS = ('forks_count', 'subscribers_count',  'stargazers_count', 'open_issues_count')


class GithubTask(BaseTask):
    description = 'Collects statistics using Github API'
    _analysis_name = "github_details"
    schema_ref = SchemaRef(_analysis_name, '1-0-4')
    # used for testing
    _repo_name = None
    _repo_url = None

    @classmethod
    def create_test_instance(cls, repo_name, repo_url):
        instance = super().create_test_instance()
        # set for testing as we are not querying DB for mercator results
        instance._repo_name = repo_name
        instance._repo_url = repo_url
        return instance

    @staticmethod
    def _retry_no_cached(call, sleep_time=2, retry_count=10):
        """ Deal with cached results from GitHub as PyGitHub does not check this

        https://developer.github.com/v3/repos/statistics/#a-word-about-caching
        """
        result = None

        for _ in range(retry_count):
            result = call()
            if result:
                break
            time.sleep(sleep_time)

        return result

    @classmethod
    def _get_last_years_commits(cls, repo):
        activity = cls._retry_no_cached(repo.get_stats_commit_activity)
        if not activity:
            return []
        return [x.total for x in activity]

    @staticmethod
    def _rate_limit_exceeded(gh):
        return gh.rate_limiting[0] == 0

    @classmethod
    def _get_repo_stats(cls, repo):
        # len(list()) is workaround for totalCount being None
        # https://github.com/PyGithub/PyGithub/issues/415
        contributors = cls._retry_no_cached(repo.get_contributors)
        d = {'contributors_count': len(list(contributors)) if contributors is not None else 'N/A'}
        for prop in REPO_PROPS:
            d[prop] = repo.raw_data.get(prop, -1)
        return d

    def _get_repo_name(self, url):
        """Retrieve GitHub repo from a preceding Mercator scan"""
        parsed = parse_gh_repo(url)
        if not parsed:
            self.log.debug('Could not parse Github repo URL %s', url)
        else:
            self._repo_url = 'https://github.com/' + parsed
        return parsed

    def _get_topics(self):
        if not self._repo_url:
            return []

        pop = requests.get('{url}'.format(url=self._repo_url))
        poppage = BeautifulSoup(pop.text, 'html.parser')

        topics = []
        for link in poppage.find_all("a", class_="topic-tag"):
            topics.append(link.text.strip())

        return topics

    def execute(self, arguments):
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

        token = self.configuration.github_token
        if not token:
            if self._rate_limit_exceeded(github.Github()):
                self.log.error("No Github API token provided (GITHUB_TOKEN env variable), "
                               "and rate limit exceeded! "
                               "Ending now to not wait endlessly")
                result_data['status'] = 'error'
                return result_data
            else:
                self.log.warning("No Github API token provided (GITHUB_TOKEN env variable), "
                                 "requests will be unauthenticated, "
                                 "i.e. limited to 60 per hour")
        else:
            # there might be more comma-separated tokens, randomly select one
            token = random.choice(token.split(',')).strip()

        gh = github.Github(login_or_token=token)
        try:
            repo = gh.get_repo(full_name_or_id=self._repo_name, lazy=False)
        except github.GithubException as e:
            self.log.exception(str(e))
            result_data['status'] = 'error'
            return result_data

        result_data['status'] = 'success'

        issues = {}
        # Get Repo Statistics
        notoriety = self._get_repo_stats(repo)
        if notoriety:
            issues.update(notoriety)
        issues['topics'] = self._get_topics()

        # Get Commit Statistics
        last_year_commits = self._get_last_years_commits(repo)
        commits = {'last_year_commits': {'sum': sum(last_year_commits),
                                         'weekly': last_year_commits}}
        issues.update(commits)
        result_data['details'] = issues
        return result_data


class GitReadmeCollectorTask(BaseTask):
    """ Store README files stored on Github """

    _GITHUB_README_PATH = 'https://raw.githubusercontent.com/{project}/{repo}/master/README{extension}'

    # Based on https://github.com/github/markup#markups
    # Markup type to its possible extensions mapping, we use OrderedDict as we check the most used types first
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
        repo_tuple = parse_gh_repo(url)
        if repo_tuple:
            project, repo = repo_tuple.split('/')
        else:
            return None

        for readme_type, extensions in self.README_TYPES.items():
            for extension in extensions:
                if extension:
                    extension = '.' + extension
                url = self._GITHUB_README_PATH.format(project=project, repo=repo, extension=extension)
                response = requests.get(url)
                if response.status_code != 200:
                    self.log.debug('No README%s found for type "%s" at "%s"', extension, readme_type, url)
                    continue

                self.log.debug('README%s found for type "%s" at "%s"', extension, readme_type, url)
                return {'type': readme_type, 'content': response.text}

    def run(self, arguments):
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('url'))

        readme = self._get_github_readme(arguments['url'])
        if not readme:
            self.log.warning("No README file found for '%s/%s'", arguments['ecosystem'], arguments['name'])

        return readme
