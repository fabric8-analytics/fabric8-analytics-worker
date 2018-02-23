# -*- coding: utf-8 -*-

import pytest

from f8a_worker.workers import GithubTask
from . import instantiate_task


@pytest.mark.usefixtures("dispatcher_setup")
class TestGithuber(object):

    @pytest.mark.parametrize(('repo_name', 'repo_url'), [
        ('projectatomic/atomic-reactor', 'https://github.com/projectatomic/atomic-reactor'),
    ])
    def test_execute(self, repo_name, repo_url):
        task = instantiate_task(cls=GithubTask, task_name='github_details')
        # set for testing as we are not querying DB for mercator results
        task._repo_name = repo_name
        task._repo_url = repo_url
        results = task.execute(arguments={})
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert set(results['details'].keys()) == {'forks_count',
                                                  'last_year_commits',
                                                  'open_issues_count',
                                                  'stargazers_count',
                                                  'subscribers_count',
                                                  'contributors_count',
                                                  'topics',
                                                  'license'}
        assert results['details']['forks_count'] > 0
        assert set(results['details']['last_year_commits'].keys()) == {'sum', 'weekly'}
        assert results['details']['license'] == {'key': 'bsd-3-clause',
                                                 'name': 'BSD 3-Clause "New" or "Revised" License',
                                                 'spdx_id': 'BSD-3-Clause',
                                                 'url':
                                                     'https://api.github.com/licenses/bsd-3-clause'}
        assert isinstance(results['details']['last_year_commits']['sum'], int)
        assert results['status'] == 'success'
