# -*- coding: utf-8 -*-

"""Tests for the GithubTask worker task."""

import pytest

from f8a_worker.workers import GoCVEpredictorTask as gocve
from unittest import mock
from selinon import FatalTaskError


@pytest.mark.usefixtures("dispatcher_setup")
class TestGocvecollector(object):
    """Tests for the Golang CVE ingestion worker task.
    """
    configuration = mock.Mock()
    configuration.select_random_github_token = mock.Mock()
    configuration.select_random_github_token.return_value = ['a', 'b']
    GITHUB_API_URL = 'https://api.github.com/repos/'
    GITHUB_URL = 'https://github.com/'
    GITHUB_TOKEN = ''
    get_response_issues = mock.Mock()
    get_response_issues.return_value = {
        "url": "https://api.github.com/repos/kubeup/archon/issues/4",
        "repository_url": "https://api.github.com/repos/kubeup/archon",
        "comments_url": "https://api.github.com/repos/kubeup/archon/issues/4/comments",
        "number": 4,
        "title": "how to generate types.generated.go",
        "created_at": "2017-03-27T12:52:28Z",
        "updated_at": "2017-03-27T14:03:20Z",
        "body": "could u support a script for generate *.generated.go in this project?",
    }

    _processJSonIssuePR = mock.Mock()
    _processJSonIssuePR.return_value = {
        "githublink": "https://github.com/kubeup/archon",
        "issue": "how to generate types.generated.go\ncould u "
                 "support a script for generate *.generated.go in this "
                 "project?",
        "number": 4,
        "package": "kubeup/archon"
    }

    log = mock.Mock()

    def test_execute_noarg(self):
        """Tests for the Golang CVE ingestion worker with no argument.
        """
        results = gocve.execute(self, arguments={})
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'package', 'details', 'status', 'summary'}
        assert results['status'] == 'unknown'

    def test_execute(self):
        """Tests for the Golang CVE ingestion worker with argument.
        """
        results = gocve.execute(self, arguments={'event': 'issue', 'number': '4',
                                                 'package': 'kubeup/archon',
                                                 'repository': 'kubeup/archon'})
        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'package', 'details', 'status', 'summary'}
        assert results['status'] == 'success'

    def test_exception(self):
        """Tests for the Golang CVE ingestion worker with argument and no Proper Git Token.
        """
        self.configuration.select_random_github_token.return_value = ''
        with pytest.raises(FatalTaskError):
            gocve.execute(self, arguments={'event': 'issue', 'number': '4',
                                           'package': 'kubeup/archon',
                                           'repository': 'kubeup/archon'})
