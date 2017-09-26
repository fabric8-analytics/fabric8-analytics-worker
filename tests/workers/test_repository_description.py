import pytest

from selinon import FatalTaskError
from f8a_worker.workers import RepositoryDescCollectorTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestRepositoryDescCollectorTask(object):
    @pytest.mark.parametrize('args', [
         {'ecosystem': 'npm', 'name': 'serve-static'},
         {'ecosystem': 'pypi', 'name': 'celery'}
    ])
    def test_execute(self, args):
        task = RepositoryDescCollectorTask.create_test_instance(
            task_name='RepositoryDescCollectorTask')
        result = task.execute(arguments=args)

        assert isinstance(result, str)
        assert result

    @pytest.mark.parametrize('args', [
         {'ecosystem': 'pypi',
          'name': 'somenonexistentpackagethatwillneverexisreallyreallywontexist'},
         {'ecosystem': 'npm',
          'name': 'somenonexistentpackagethatwillneverexisreallyreallywontexist'}
    ])
    def test_execute_nonexistent(self, args):
        task = RepositoryDescCollectorTask.create_test_instance(
            task_name='RepositoryDescCollectorTask')

        with pytest.raises(FatalTaskError):
            task.execute(arguments=args)

    @pytest.mark.parametrize('args', [
         {'ecosystem': 'maven', 'name': 'foo'},
         {'ecosystem': 'nuget', 'name': 'bar'},
         {'ecosystem': 'go', 'name': 'bar'}
    ])
    def test_execute_unsupported_ecosystem(self, args):
        task = RepositoryDescCollectorTask.create_test_instance(
            task_name='RepositoryDescCollectorTask')

        with pytest.raises(FatalTaskError):
            task.execute(arguments=args)
