import os
import errno
import itertools

import flexmock
import pytest
import requests

from uuid import uuid4

from sqlalchemy import (create_engine, Column, String)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
Base = declarative_base()

from cucoslib.conf import get_configuration, get_postgres_connection_string
from cucoslib.enums import EcosystemBackend
from cucoslib.errors import TaskError
from cucoslib.models import (Analysis, Ecosystem, Package, Version, create_db_scoped_session)
from cucoslib import utils # so that we can mock functions from here
from cucoslib.utils import (get_all_files_from,
                            get_analysis,
                            hidden_path_filter,
                            skip_git_files,
                            DictList,
                            ThreadPool,
                            MavenCoordinates,
                            mvn_find_latest_version,
                            epv2repopath,
                            compute_digest,
                            get_latest_upstream_details,
                            safe_get_latest_version,
                            DownstreamMapCache,
                            parse_release_str,
                            parse_gh_repo)

from .conftest import rdb

configuration = get_configuration()


class TestUtilFunctions(object):
    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

    def test_dictlist(self):
        dl = DictList()
        dl['a'] = 1
        dl['a'] = 2
        assert dl.get_one('a') == 1
        assert dl['a'] == [1, 2]

    def test_get_all_files_from(self, tmpdir):
        test_dir = os.path.abspath(str(tmpdir))

        def touch_file(path):
            abspath = os.path.join(test_dir, path)
            abs_dir_path = os.path.dirname(abspath)
            try:
                os.makedirs(abs_dir_path)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    # was created in previous iteration
                    pass
            with open(abspath, "w") as fd:
                fd.write("banana")

        py_files = {
            os.path.join(test_dir, 'test_path/file.py'),
            os.path.join(test_dir, 'test_path/some.py'),
        }
        test_files = {
            os.path.join(test_dir, 'test_path/test'),
        }
        hidden_files = {
            os.path.join(test_dir, 'test_path/.hidden'),
        }
        git_files = {
            os.path.join(test_dir, 'test_path/.git/object'),
        }
        all_files = set(itertools.chain(py_files, test_files, hidden_files, git_files))
        for f in all_files:
            touch_file(f)

        assert set(get_all_files_from(test_dir)) == all_files
        assert set(get_all_files_from(test_dir, path_filter=skip_git_files)) == \
            set(itertools.chain(py_files, test_files, hidden_files))
        assert set(get_all_files_from(test_dir, file_filter=lambda x: x.endswith('.py'))) == \
            py_files
        assert set(get_all_files_from(test_dir, path_filter=hidden_path_filter)) == \
            set(itertools.chain(py_files, test_files))

    def test_mvn_find_latest_version(self):
        repo_url = os.path.join(os.path.dirname(__file__), 'data/maven/')
        a = MavenCoordinates('org.junit', 'junit')
        latest = mvn_find_latest_version(repo_url, a)
        assert latest == '4.12'

    def test_parse_release_str(self):
        assert parse_release_str('npm:arrify:1.0.1') == ('npm', 'arrify', '1.0.1')
        assert parse_release_str('maven:junit:junit:4.12') == ('maven', 'junit:junit', '4.12')

    def test_epv2repopath(self):
        npm = Ecosystem(name='npm', backend=EcosystemBackend.npm)
        rg = Ecosystem(name='rubygems', backend=EcosystemBackend.rubygems)
        pp = Ecosystem(name='pypi', backend=EcosystemBackend.pypi)
        mvn = Ecosystem(name='maven', backend=EcosystemBackend.maven)
        result = epv2repopath(npm, 'arrify', '1.0.1')
        assert result == 'arrify/-/arrify-1.0.1.tgz'
        result = epv2repopath(npm, 'arrify', '1.0.1', repo_name='npm-cache')
        assert result == 'npm-cache/arrify/-/arrify-1.0.1.tgz'
        result = epv2repopath(npm, 'arrify', '1.0.1',
                              repo_url='artifactory.example.com:8081/artifactory/')
        assert result == 'arrify/-/arrify-1.0.1.tgz'
        result = epv2repopath(npm, 'arrify', '1.0.1',
                              repo_url='http://artifactory.example.com:8081/artifactory/',
                              repo_name='npm-cache')
        assert result == 'http://artifactory.example.com:8081/artifactory/npm-cache/arrify/-/arrify-1.0.1.tgz'
        # same as previous, but this time repo_url is missing trailing slash
        result = epv2repopath(npm, 'arrify', '1.0.1',
                              repo_url='http://artifactory.example.com:8081/artifactory',
                              repo_name='npm-cache')
        assert result == 'http://artifactory.example.com:8081/artifactory/npm-cache/arrify/-/arrify-1.0.1.tgz'

        result = epv2repopath(rg, 'rake', '11.1.2')
        assert result == 'gems/rake-11.1.2.gem'
        result = epv2repopath(pp, 'requests', '2.9.1')
        assert result == 'source/r/requests/requests-2.9.1.tar.gz'
        result = epv2repopath(mvn, 'org.junit:junit', '4.12')
        assert result == 'org/junit/junit/4.12/junit-4.12.jar'

    def test_compute_digest(self):
        assert compute_digest("/etc/os-release")
        with pytest.raises(TaskError):
            assert compute_digest("/", raise_on_error=True)
        assert compute_digest("/") is None


class TestThreadPool(object):
    def test_context_manager(self):
        s = set()

        def foo(x):
            s.add(x)

        original = set(range(0, 10))
        with ThreadPool(foo) as tp:
            for i in original:
                tp.add_task(i)

        assert s == original

    def test_normal_usage(self):
        s = set()

        def foo(x):
            s.add(x)

        original = set(range(0, 10))
        tp = ThreadPool(foo)
        for i in original:
            tp.add_task(i)
        tp.start()
        tp.join()
        assert s == original


example_coordinates = [
        # MavenCoordinates(), from_str, is_from_str_ok, to_str, to_str(omit_version=True), to_repo_url
        (MavenCoordinates('g', 'a'), 'g:a', True, 'g:a', 'g:a', None),
        (MavenCoordinates('g', 'a', '1'), 'g:a:1', True, 'g:a:1', 'g:a', 'g/a/1/a-1.jar'),
        (MavenCoordinates('g', 'a', packaging='war'), 'g:a:war:', True, 'g:a:war:', 'g:a:war:', None),
        (MavenCoordinates('g', 'a', '1', packaging='war'), ['g:a:war:1', 'g:a:war::1'], True, 'g:a:war:1', 'g:a:war:', 'g/a/1/a-1.war'),
        (MavenCoordinates('g', 'a', classifier='sources'), 'g:a::sources:', True, 'g:a::sources:', 'g:a::sources:', None),
        (MavenCoordinates('g', 'a', '1', classifier='sources'), 'g:a::sources:1', True, 'g:a::sources:1', 'g:a::sources:', 'g/a/1/a-1-sources.jar'),
        (MavenCoordinates('g', 'a', packaging='war', classifier='sources'), 'g:a:war:sources:', True, 'g:a:war:sources:', 'g:a:war:sources:', None),
        (MavenCoordinates('g', 'a', '1', packaging='war', classifier='sources'), 'g:a:war:sources:1', True, 'g:a:war:sources:1', 'g:a:war:sources:', 'g/a/1/a-1-sources.war'),
        (MavenCoordinates('org.fedoraproject', 'test-artifact', '1.0-beta1'), 'org.fedoraproject:test-artifact:1.0-beta1', True, 'org.fedoraproject:test-artifact:1.0-beta1', 'org.fedoraproject:test-artifact', 'org/fedoraproject/test-artifact/1.0-beta1/test-artifact-1.0-beta1.jar'),
        # No colon in from_str
        (MavenCoordinates('g', 'a', '1'), 'ga1', False, None, None, None),
        # Too many colons in from_str
        (MavenCoordinates('g', 'a', '1', packaging='war', classifier='sources'), 'g:a:war:sources:1:', False, None, None, None),
    ]


class TestMavenCoordinates(object):
    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str', 'to_str_omit_version', 'to_repo_url'),
                             example_coordinates)
    def test_from_str(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version, to_repo_url):
        from_strings = from_str if isinstance(from_str, list) else [from_str]
        for fstr in from_strings:
            if is_from_str_ok:
                assert MavenCoordinates.from_str(fstr) == coords
            else:
                with pytest.raises(ValueError):
                    MavenCoordinates.from_str(fstr)

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str', 'to_str_omit_version', 'to_repo_url'),
                             example_coordinates)
    def test_to_str(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version, to_repo_url):
        if to_str:
            assert coords.to_str() == to_str
        if to_str_omit_version:
            assert coords.to_str(omit_version=True) == to_str_omit_version

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str', 'to_str_omit_version', 'to_repo_url'),
                             example_coordinates)
    def test_to_repo_url(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version, to_repo_url):
        if to_repo_url:
            assert coords.to_repo_url() == to_repo_url


class TestGetAnalysis(object):
    def setup_method(self, method):
        # we cannot use this with pytest.mark.usefixtures, since that runs *after* setup_method
        #    which means it wouldn't clean up the DB before we try to create the test ecosystem
        rdb()
        self.s = create_db_scoped_session()
        self.e = Ecosystem(name='npm', backend=EcosystemBackend.npm)
        self.p = Package(name='serve-static', ecosystem=self.e)
        self.v = Version(identifier='1.7.1', package=self.p)
        self.a = Analysis(version=self.v)
        self.s.add(self.a)
        self.s.commit()

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_analysis_exists(self):
        a = get_analysis('npm', 'serve-static', '1.7.1')
        assert a.id == self.a.id

    @pytest.mark.usefixtures("dispatcher_setup")
    def test_analysis_doesnt_exist(self):
        assert get_analysis('npm', 'serve-static', '1.7.2') is None


class TestGetAnityaProject(object):
    def test_basic(self):
        resp = flexmock(json=lambda: {'a': 'b'},
                        raise_for_status=lambda: None)
        url = configuration.anitya_url + '/api/by_ecosystem/foo/bar'
        flexmock(requests).should_receive('get').with_args(url).and_return(resp)
        assert get_latest_upstream_details('foo', 'bar') == {'a': 'b'}

    def test_bad_status(self):
        resp = flexmock(json=lambda: {'a': 'b'})
        resp.should_receive('raise_for_status').and_raise(Exception())
        url = configuration.anitya_url + '/api/by_ecosystem/foo/bar'
        flexmock(requests).should_receive('get').with_args(url).and_return(resp)
        with pytest.raises(Exception):
            get_latest_upstream_details('foo', 'bar')


class TestSafeGetLatestVersion(object):
    def test_basic(self):
        flexmock(utils).should_receive('get_latest_upstream_details').\
            with_args('foo', 'bar').and_return({'versions': ['1']})
        assert safe_get_latest_version('foo', 'bar') == '1'

    def test_anitya_error(self):
        flexmock(utils).should_receive('get_latest_upstream_details').\
            with_args('foo', 'bar').and_raise(requests.exceptions.RequestException())
        assert safe_get_latest_version('foo', 'bar') is None

        flexmock(utils).should_receive('get_latest_upstream_details').\
            with_args('foo', 'bar').and_return({'versions': []})
        assert safe_get_latest_version('foo', 'bar') is None


class TestDownstreamMapCache(object):
    def test_set_get(self):
        class DownstreamMap(Base):
            __tablename__ = 'downstream_map'
            key = Column(String(255), primary_key=True)
            value = Column(String(512), nullable=False)

        connection_string = get_postgres_connection_string()
        engine = create_engine(connection_string)
        session = sessionmaker(bind=engine)()
        Base.metadata.create_all(engine)
        r = DownstreamMapCache(session)

        key = uuid4().hex
        value = uuid4().hex
        r[key] = value
        assert r[key] == value

        # test update
        value = 'new value'
        r[key] = value
        assert r[key] == value


class TestParseGHRepo:
    @pytest.mark.parametrize('url', [
        'github.com/foo/bar',
        'github.com/foo/bar.git',
        'www.github.com/foo/bar',
        'http://github.com/foo/bar',
        'http://github.com/foo/bar.git',
        'git+https://www.github.com/foo/bar',
        'git@github.com:foo/bar',
        'git@github.com:foo/bar.git',
        'git+ssh@github.com:foo/bar.git',
        'ssh://git@github.com:foo/bar.git',
    ])
    def test_parse_gh_repo_ok(self, url):
        assert parse_gh_repo(url) == 'foo/bar'

    @pytest.mark.parametrize('url', [
        'gitlab.com/foo/bar',
        'git@gitlab.com:foo/bar.git',
        'https://bitbucket.org/foo/bar',
        'something',
        'something@else',
    ])
    def test_parse_gh_repo_nok(self, url):
        assert parse_gh_repo(url) is None
