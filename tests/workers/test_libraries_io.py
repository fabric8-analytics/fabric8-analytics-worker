import pytest

from f8a_worker.workers import LibrariesIoTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestLibrariesIoTask(object):
    @pytest.mark.parametrize('args', [
         {'ecosystem': 'maven', 'name': 'org.jboss.netty:netty'},
         {'ecosystem': 'npm', 'name': 'grunt'},
         {'ecosystem': 'pypi', 'name': 'Flask'},
         {'ecosystem': 'nuget', 'name': 'Newtonsoft.Json'}
    ])
    def test_execute(self, args):
        task = LibrariesIoTask.create_test_instance(task_name='libraries_io')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert set(results['details'].keys()) == {'releases',
                                                  'dependents',
                                                  'dependent_repositories'}
        releases = results['details']['releases']
        assert releases.get('count')
        assert releases.get('latest', {}).get('published_at')
        dependents = results['details']['dependents']
        assert dependents.get('count')
        dependent_repos = results['details']['dependent_repositories']
        assert dependent_repos.get('count')
        assert dependent_repos.get('top')
