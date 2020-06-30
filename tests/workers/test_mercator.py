"""Tests for the MercatorTask worker task."""

import os
from pathlib import Path
import pytest
from flexmock import flexmock
from f8a_worker.object_cache import EPVCache
from f8a_worker.process import IndianaJones
from f8a_worker.workers.mercator import MercatorTask, _validate_utf_json


def compare_dictionaries(a, b):
    """Compare two dictionaries (shape+content)."""
    def mapper(item):
        if isinstance(item, list):
            return frozenset(map(mapper, item))
        if isinstance(item, dict):
            return frozenset({mapper(k): mapper(v) for k, v in item.items()}.items())
        return item

    return mapper(a) == mapper(b)


@pytest.mark.usefixtures("dispatcher_setup")
class TestMercator(object):
    """Tests for the MercatorTask worker task."""

    def setup_method(self, method):
        """Set up the MercatorTask."""
        self.m = MercatorTask.create_test_instance(task_name='metadata')
        assert method

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute_npm(self, tmpdir, npm):
        """Test the MercatorTask for the NPM ecosystem."""
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
    def test_execute_maven(self, maven):
        """Test the MercatorTask for the Maven ecosystem."""
        # TODO: reduce cyclomatic complexity
        pom_path = str(Path(__file__).parent.parent / 'data/maven/com.networknt/mask/pom.xml')
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

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute_go(self, go):
        """Test the MercatorTask for the Go ecosystem."""
        path = str(Path(__file__).parent.parent / 'data/go/no-glide')
        args = {'ecosystem': go.name, 'name': 'dummy', 'version': 'dummy'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(path)
        results = self.m.execute(arguments=args)

        assert isinstance(results, dict) and results
        details = results['details'][0]
        assert set(details['dependencies']) == {'github.com/fabric8-analytics/mercator-go',
                                                'github.com/go-yaml/yaml'}

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute_go_glide(self, go):
        """Test the MercatorTask for the Go ecosystem (project includes Glide files)."""
        path = str(Path(__file__).parent.parent / 'data/go/glide')
        args = {'ecosystem': go.name, 'name': 'dummy', 'version': 'dummy'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(path)
        results = self.m.execute(arguments=args)

        assert isinstance(results, dict) and results
        details = results['details'][0]
        assert details['ecosystem'] == 'go-glide'
        assert details['name'] == 'github.com/fabric8-analytics/mercator-go/handlers/golang_handler'
        assert set(details['dependencies']) == {'github.com/Masterminds/glide/cfg ~0.13.1'}
        assert set(details['_dependency_tree_lock'].keys()) == {'dependencies', 'hash', 'updated'}
        assert set(details['_dependency_tree_lock']['dependencies'][0].keys()) > {'name', 'version'}

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute_go_godeps(self, go):
        """Test the MercatorTask for the Go ecosystem (project includes Godeps.json files)."""
        path = str(Path(__file__).parent.parent / 'data/go/godeps')
        args = {'ecosystem': go.name, 'name': 'github.com/test/test', 'version': 'ffff'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(path)
        results = self.m.execute(arguments=args)

        assert isinstance(results, dict) and results
        details = results['details'][0]
        assert details['ecosystem'] == 'go-godeps'
        assert details['name'] == 'github.com/test/test'
        assert details['version'] == 'ffff'
        assert set(details['dependencies']) == {
            'vbom.ml/util/sortorder db5cfe13f5cc80a4990d98e2e1b0707a4d1a5394'
        }

    @staticmethod
    def sort_by_path(dict_):
        """Sort dict_ by length of 'path' of it's members."""
        return sorted(dict_, key=lambda a: len(a['path'].split(os.path.sep)))

    def test_get_outermost_items(self):
        """Test get_outermost_items()."""
        d = [{'path': '/a/b/c/d'}, {'path': '/a/b/c'}, {'path': '/a'}]
        assert self.m.get_outermost_items(d) == [{'path': '/a'}]

        d = [{'path': 'bbb'}, {'path': 'a/b/c/'}]
        assert self.m.get_outermost_items(d) == [{'path': 'bbb'}]

        d = [{'path': '/a/b'}, {'path': '/b/c'}, {'path': '/c/d/e'}]
        expected = self.sort_by_path([{'path': '/a/b'}, {'path': '/b/c'}])
        result = self.sort_by_path(self.m.get_outermost_items(d))
        assert len(result) == len(expected)
        for i in range(len(expected)):
            assert compare_dictionaries(result[i], expected[i])


def test_validate_utf_json():
    """Test the function to remove non UTF-8 characters from description if present."""
    assert _validate_utf_json(None) is None
    assert _validate_utf_json({'details': [{'description': 'test description'}]}) == \
           {'details': [{'description': 'test description'}]}
    assert _validate_utf_json({'details': [{
        'description': '��C\x00h\x00a\x00n\x00g\x00e\x00 \x001\x00'}]}) == \
        {'details': [{'description': 'Change 1'}]}
    assert _validate_utf_json({'details': []}) == {'details': []}
    assert _validate_utf_json({'details': {}}) == {'details': {}}
    assert _validate_utf_json({'details': [{'description': None}]}) == \
           {'details': [{'description': None}]}
