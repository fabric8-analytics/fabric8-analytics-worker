# -*- coding: utf-8 -*-

from github.GithubException import RateLimitExceededException
import pytest

from cucoslib.workers import GithubTask


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
                                                  'updated_issues',
                                                  'updated_pull_requests',
                                                  'contributors_count',
                                                  'topics'}
        assert results['details']['forks_count'] > 0
        assert set(results['details']['last_year_commits'].keys()) == {'sum', 'weekly'}
        assert isinstance(results['details']['last_year_commits']['sum'], int)
        assert set(results['details']['updated_issues'].keys()) == {'year', 'month'}
        assert set(results['details']['updated_issues']['year'].keys()) == {'opened', 'closed'}
        assert set(results['details']['updated_issues']['month'].keys()) == {'opened', 'closed'}
        assert set(results['details']['updated_pull_requests'].keys()) == {'year', 'month'}
        assert set(results['details']['updated_pull_requests']['year'].keys()) == {'opened', 'closed'}
        assert set(results['details']['updated_pull_requests']['month'].keys()) == {'opened', 'closed'}
        assert results['status'] == 'success'
