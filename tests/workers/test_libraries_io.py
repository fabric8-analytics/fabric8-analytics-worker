"""Tests for LibrariesIoTask."""

import time
from flexmock import flexmock
import pytest
from flaky import flaky
from requests.exceptions import HTTPError

from f8a_worker.defaults import F8AConfiguration
from f8a_worker.errors import TaskError
from f8a_worker.workers import LibrariesIoTask


def rerun_http_error(err, *args):
    """Retry on HTTP errors, with a delay."""
    assert args
    if not issubclass(err[0], HTTPError):
        # Not an HTTP error, do not retry
        return False

    time.sleep(10)
    return True


@pytest.mark.usefixtures("dispatcher_setup")
class TestLibrariesIoTask(object):
    """Tests for LibrariesIoTask."""

    @flaky(max_runs=6, min_passes=1, rerun_filter=rerun_http_error)
    @pytest.mark.usefixtures("npm")
    @pytest.mark.parametrize('args', [
         {'ecosystem': 'npm', 'name': 'grunt'},
    ])
    def test_execute(self, args):
        """Test proper function."""
        task = LibrariesIoTask.create_test_instance(task_name='libraries_io')
        flexmock(F8AConfiguration, LIBRARIES_IO_TOKEN='no-token')
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

    @flaky(max_runs=6, min_passes=1, rerun_filter=rerun_http_error)
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
