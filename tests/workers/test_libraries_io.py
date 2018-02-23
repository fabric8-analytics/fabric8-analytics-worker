"""Tests for LibrariesIoTask."""

from flexmock import flexmock
import pytest

from f8a_worker.defaults import F8AConfiguration
from f8a_worker.errors import TaskError
from f8a_worker.workers import LibrariesIoTask

from . import instantiate_task


@pytest.mark.usefixtures("dispatcher_setup")
class TestLibrariesIoTask(object):
    """Tests for LibrariesIoTask."""

    @pytest.mark.parametrize('args', [
         {'ecosystem': 'npm', 'name': 'grunt'},
    ])
    def test_execute(self, args):
        """Test proper function."""
        task = instantiate_task(cls=LibrariesIoTask, task_name='libraries_io')
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

    @pytest.mark.parametrize('args', [
         {'ecosystem': 'maven', 'name': 'madeup.group:nonexistent.id'},
    ])
    def test_execute_nonexistent(self, args):
        """Run task for nonexistent package."""
        task = instantiate_task(cls=LibrariesIoTask, task_name='libraries_io')
        flexmock(F8AConfiguration, LIBRARIES_IO_TOKEN='no-token')
        with pytest.raises(TaskError):
            task.execute(arguments=args)
