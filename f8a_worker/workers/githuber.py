"""
sample output:
{
  "details": {
    "open_issues_count": 38,
    "updated_issues": {
      "year": {
        "opened": 2,
        "closed": 0
      },
      "month": {
        "opened": 1,
        "closed": 0
      }
    },
    "updated_pull_requests": {
      "year": {
        "opened": 2,
        "closed": 2
      },
      "month": {
        "opened": 1,
        "closed": 1
      }
    },
    "subscribers_count": 11,
    "last_year_commits": {
      "sum": 0,
      "weekly": [...]
     },
     "forks_count": 20,
     "stargazers_count": 48
   },
   "summary": []
}
"""

import bs4
import requests
import datetime
import github
import random
import time
from collections import OrderedDict

from f8a_worker.schemas import SchemaRef
from f8a_worker.base import BaseTask
from f8a_worker.utils import parse_gh_repo

ISSUE_PROPS = ('created_at', 'closed_at', 'updated_at', 'id', 'pull_request', 'state')
REPO_PROPS = ('forks_count', 'subscribers_count',  'stargazers_count', 'open_issues_count')
DAYS_BACK = 14  # info about updated issues & PRs max DAYSBACK days old
MONTH_BACK = 30 # info about updated issues & PRs month old
YEAR_BACK = 365 # info about updated issues & PRs year old


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

    def _issues_or_prs_count(self, gh, query):
        # Check the rate-limit for Github API first. Apply retry if needed
        if self._rate_limit_exceeded(gh):
            retrytime = gh.rate_limiting_resettime - int(datetime.datetime.now().timestamp()) + 10
            self.log.info("Github rate-limit exceeded, retrying in %d seconds", retrytime)
            self.retry(countdown=retrytime)
        items = gh.search_issues(query=query)
        return getattr(items, 'totalCount', -1)

    @classmethod
    def _get_repo_stats(cls, repo):
        # len(list()) is workaround for totalCount being None
        # https://github.com/PyGithub/PyGithub/issues/415
        contributors = cls._retry_no_cached(repo.get_contributors)
        d = {'contributors_count': len(list(contributors)) if contributors is not None else 'N/A'}
        for prop in REPO_PROPS:
            d[prop] = repo.raw_data.get(prop, -1)
        return d

    def _query_repo_name(self):
        """Retrieve GitHub repo from a preceding Mercator scan"""
        # Fridolin: most of the checks can be removed since Dispatcher schedules this task iff we have github.com
        wr = self.parent_task_result('metadata')
        if wr is None:
            self.log.error("No repo_name provided, and no Mercator scan result")
            return None
        code_repos =\
            [m.get("code_repository") for m in wr.get('details', []) if m.get("code_repository")]
        repo_details = code_repos[0] if code_repos else None
        if repo_details is None:
            self.log.debug("No repo_name provided, and no repo metadata found")
            return None
        repo_name = repo_details.get("url")
        if repo_name is None:
            self.log.debug('No repo name extracted, nothing to do')
            return None
        parsed = parse_gh_repo(repo_name)
        if not parsed:
            self.log.debug('Could not parse Github repo URL %s', repo_name)
        else:
            self._repo_url = 'https://github.com/' + parsed
        return parsed

    def _get_topics(self):
        if not self._repo_url:
            return []

        pop = requests.get('{url}'.format(url=self._repo_url))
        poppage = bs4.BeautifulSoup(pop.text, 'html.parser')

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
            self._repo_name = self._query_repo_name()
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

        # Get Count of Issues and PRs for last year and last month
        now = datetime.datetime.utcnow()
        month = (now - datetime.timedelta(days=MONTH_BACK)).strftime('%Y-%m-%dT%H:%M:%SZ')
        year = (now - datetime.timedelta(days=YEAR_BACK)).strftime('%Y-%m-%dT%H:%M:%SZ')
        now = now.strftime('%Y-%m-%dT%H:%M:%SZ')

        issues_closed_year = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' closed:' + year + '..' + now + ' type:issue')
        issues_closed_month = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' closed:' + month + '..' + now + ' type:issue')
        prs_closed_year = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' closed:' + year + '..' + now + ' type:pr')
        prs_closed_month = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' closed:' + month + '..' + now + ' type:pr')

        issues_opened_year= self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' created:' + year + '..' + now + ' type:issue')
        issues_opened_month = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' created:' + month + '..' + now + ' type:issue')
        prs_opened_year = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' created:' + year + '..' + now + ' type:pr')
        prs_opened_month = self._issues_or_prs_count(gh, query='repo:' + repo.full_name + ' created:' + month + '..' + now + ' type:pr')

        issues = {'updated_issues': {'year': {'opened': issues_opened_year, 'closed': issues_closed_year},
                                    'month': {'opened': issues_opened_month, 'closed': issues_closed_month}},
                 'updated_pull_requests': {'year': {'opened': prs_opened_year, 'closed': prs_closed_year},
                                           'month': {'opened': prs_opened_month, 'closed': prs_closed_month}}}

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
        ('Unknown', ('')),
    ))

    def _get_github_repo_tuple(self):
        repo_url = self.parent_task_result('metadata')['details'][0]['code_repository']['url']
        repo_tuple = parse_gh_repo(repo_url)
        return repo_tuple.split('/')

    def _get_github_readme(self):
        project, repo = self._get_github_repo_tuple()

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

        readme = self._get_github_readme()
        if not readme:
            self.log.warning("No README file found for '%s/%s'", arguments['ecosystem'], arguments['name'])

        return readme
