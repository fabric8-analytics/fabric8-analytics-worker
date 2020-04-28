"""Tests for LibrariesIoTask."""

from flexmock import flexmock
import pytest
from unittest.mock import patch
from f8a_worker.defaults import F8AConfiguration
from f8a_worker.errors import TaskError
from f8a_worker.workers.libraries_io import LibrariesIoTask

val_json = {
    "dependent_repos_count": 386381,
    "dependents_count": 39369,
    "description": "The JavaScript Task Runner",
    "forks": 1549,
    "homepage": "https://gruntjs.com/",
    "language": "JavaScript",
    "latest_download_url": "https://registry.npmjs.org/grunt/-/grunt-1.1.0.tgz",
    "package_manager_url": "https://www.npmjs.com/package/grunt",
    "platform": "NPM",
    "rank": 31,
    "repository_url": "https://github.com/gruntjs/grunt",
    "stars": 11969,
    "status": "",
    "versions": [
        {
            "number": "0.1.0",
            "published_at": "2012-01-12T13:08:51.911Z",
            "spdx_expression": "",
            "original_license": ""
        },
        {
            "number": "0.1.1",
            "published_at": "2012-01-19T15:01:53.028Z",
            "spdx_expression": "",
            "original_license": "",
            "researched_at": ""
        }
    ]
}


@pytest.mark.usefixtures("dispatcher_setup")
class TestLibrariesIoTask(object):
    """Tests for LibrariesIoTask."""

    @pytest.mark.usefixtures("npm")
    @pytest.mark.parametrize('args', [
        {'ecosystem': 'npm', 'name': 'grunt'},
    ])
    @patch("f8a_worker.workers.libraries_io.get_response")
    def test_execute(self, m1, args):
        """Test proper function."""
        task = LibrariesIoTask.create_test_instance(task_name='libraries_io')
        flexmock(F8AConfiguration, LIBRARIES_IO_TOKEN='no-token')
        m1.return_value = val_json
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert set(results['details'].keys()) == {'releases',
                                                  'dependents',
                                                  'dependent_repositories'}
        releases = results['details']['releases']
        assert releases.get('count')
        assert releases.get('recent')
        assert results['details']['dependents'].get('count')
        assert results['details']['dependent_repositories'].get('count')

    @pytest.mark.usefixtures("maven")
    @pytest.mark.parametrize('args', [
        {'ecosystem': 'maven', 'name': 'madeup.group:nonexistent.id'},
    ])
    def test_execute_nonexistent(self, args):
        """Run task for nonexistent package."""
        task = LibrariesIoTask.create_test_instance(task_name='libraries_io')
        flexmock(F8AConfiguration, LIBRARIES_IO_TOKEN='no-token')
        with pytest.raises(TaskError):
            task.execute(arguments=args)
