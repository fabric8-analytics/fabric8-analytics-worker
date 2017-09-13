import os
import pytest
from flexmock import flexmock
from f8a_worker.object_cache import EPVCache
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
    def test_execute_npm(self, tmpdir, npm):
        name = 'wrappy'
        version = '1.0.2'
        required = {'homepage', 'version', 'declared_licenses', 'code_repository',
                    'bug_reporting', 'description', 'name', 'author'}
        IndianaJones.fetch_artifact(npm, artifact=name, version=version, target_dir=str(tmpdir))

        args = {'ecosystem': npm.name, 'name': name, 'version': version}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(str(tmpdir))
        results = self.m.execute(arguments=args)

        assert isinstance(results, dict) and results
        details = results['details'][0]
        assert set(details.keys()) >= required  # check at least the required are there
        assert all([details[key] for key in list(required)])  # assert required are not None
        assert details['name'] == name

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute_maven(self, tmpdir, maven):
        pom_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    '..', 'data', 'maven', 'com.networknt', 'mask', 'pom.xml')
        name = 'com.networknt:mask'
        version = '1.1.0'
        required = {'code_repository', 'declared_licenses', 'dependencies', 'description',
                    'devel_dependencies', 'name', 'homepage', 'version'}

        args = {'ecosystem': maven.name, 'name': name, 'version': version}
        flexmock(EPVCache).should_receive('get_pom_xml').and_return(pom_path)
        results = self.m.execute(arguments=args)

        assert isinstance(results, dict) and results
        details = results['details'][0]
        assert set(details.keys()) >= required  # check at least the required are there
        assert all([details[key] for key in list(required)])  # assert required are not None
        assert details['code_repository'].get('url')
        assert details['declared_licenses'][0]
        for d in details['dependencies'] + details['devel_dependencies']:
            n, v = d.split(' ')
            assert n
            assert v
        assert details['name'] == name
        assert details['version'] == version
