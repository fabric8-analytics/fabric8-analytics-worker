# -*- coding: utf-8 -*-

from github.GithubException import RateLimitExceededException
import pytest

from f8a_worker.workers import GithubTask


@pytest.mark.xfail(raises=RateLimitExceededException)
@pytest.mark.usefixtures("dispatcher_setup")
class TestGithuber(object):

    @pytest.mark.parametrize(('repo_name', 'repo_url'), [
        ('projectatomic/atomic-reactor', 'https://github.com/projectatomic/atomic-reactor'),
    ])
    def test_execute(self, repo_name, repo_url):
        task = GithubTask.create_test_instance(repo_name, repo_url)
        results = task.execute(arguments={})
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        if not results['details'].keys():  # no github api token provided
            return
        assert set(results['details'].keys()) == {'forks_count',
                                                  'last_year_commits',
                                                  'open_issues_count',
                                                  'stargazers_count',
                                                  'subscribers_count',
                                                  'contributors_count',
                                                  'topics'}
        assert results['details']['forks_count'] > 0
        assert set(results['details']['last_year_commits'].keys()) == {'sum', 'weekly'}
        assert isinstance(results['details']['last_year_commits']['sum'], int)
        assert results['status'] == 'success'
