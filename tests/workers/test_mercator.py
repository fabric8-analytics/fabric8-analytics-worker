import pytest
from flexmock import flexmock
from f8a_worker.object_cache import EPVCache
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Ecosystem
from f8a_worker.process import IndianaJones
from f8a_worker.workers.mercator import MercatorTask


def compare_dictionaries(a, b):
    def mapper(item):
        if isinstance(item, list):
            return frozenset(map(mapper, item))
        if isinstance(item, dict):
            return frozenset({mapper(k): mapper(v) for k, v in item.items()}.items())
        return item

    return mapper(a) == mapper(b)


@pytest.mark.usefixtures("dispatcher_setup")
class TestMercator(object):
    def setup_method(self, method):
        self.m = MercatorTask.create_test_instance(task_name='metadata')

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self, tmpdir):
        npm = Ecosystem(name='npm', backend=EcosystemBackend.npm)
        flexmock(self.m.storage).should_receive('get_ecosystem').with_args('npm').and_return(npm)
        name = 'wrappy'
        version = '1.0.2'
        required = {'homepage', 'version', 'declared_licenses', 'code_repository',
                    'bug_reporting', 'description', 'name', 'author'}
        IndianaJones.fetch_artifact(
            npm, artifact=name,
            version=version, target_dir=str(tmpdir))

        args = {'ecosystem': npm.name, 'name': 'foo', 'version': 'bar'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(str(tmpdir))
        results = self.m.execute(arguments=args)
        assert results is not None
        assert isinstance(results, dict)

        details = results['details'][0]
        assert required.issubset(set(details.keys()))  # check at least the required are there
        assert all([details[key] for key in list(required)])  # assert required are not None
        assert details['name'] == name
