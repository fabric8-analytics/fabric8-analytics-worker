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

from f8a_worker.defaults import F8AConfiguration as configuration
from f8a_worker.errors import TaskError
from f8a_worker import utils  # so that we can mock functions from here
from f8a_worker.utils import (get_all_files_from,
                              hidden_path_filter,
                              skip_git_files,
                              ThreadPool,
                              MavenCoordinates,
                              compute_digest,
                              get_latest_upstream_details,
                              safe_get_latest_version,
                              DownstreamMapCache,
                              parse_gh_repo,
                              url2git_repo)


class TestUtilFunctions(object):
    def setup_method(self, method):
        pass

    def teardown_method(self, method):
        pass

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
        # MavenCoordinates(), from_str, is_from_str_ok, to_str,
        # to_str(omit_version=True), to_repo_url
        (MavenCoordinates('g', 'a'), 'g:a', True, 'g:a', 'g:a', None),
        (MavenCoordinates('g', 'a', '1'), 'g:a:1', True, 'g:a:1', 'g:a', 'g/a/1/a-1.jar'),
        (MavenCoordinates('g', 'a', packaging='war'), 'g:a:war:', True, 'g:a:war:', 'g:a:war:',
            None),
        (MavenCoordinates('g', 'a', '1', packaging='war'), ['g:a:war:1', 'g:a:war::1'], True,
            'g:a:war:1', 'g:a:war:', 'g/a/1/a-1.war'),
        (MavenCoordinates('g', 'a', classifier='sources'), 'g:a::sources:', True, 'g:a::sources:',
            'g:a::sources:', None),
        (MavenCoordinates('g', 'a', '1', classifier='sources'), 'g:a::sources:1', True,
            'g:a::sources:1', 'g:a::sources:', 'g/a/1/a-1-sources.jar'),
        (MavenCoordinates('g', 'a', packaging='war', classifier='sources'), 'g:a:war:sources:',
            True, 'g:a:war:sources:', 'g:a:war:sources:', None),
        (MavenCoordinates('g', 'a', '1', packaging='war', classifier='sources'),
            'g:a:war:sources:1', True, 'g:a:war:sources:1', 'g:a:war:sources:',
            'g/a/1/a-1-sources.war'),
        (MavenCoordinates('org.fedoraproject', 'test-artifact', '1.0-beta1'),
            'org.fedoraproject:test-artifact:1.0-beta1', True,
            'org.fedoraproject:test-artifact:1.0-beta1', 'org.fedoraproject:test-artifact',
            'org/fedoraproject/test-artifact/1.0-beta1/test-artifact-1.0-beta1.jar'),
        # No colon in from_str
        (MavenCoordinates('g', 'a', '1'), 'ga1', False, None, None, None),
        # Too many colons in from_str
        (MavenCoordinates('g', 'a', '1', packaging='war', classifier='sources'),
            'g:a:war:sources:1:', False, None, None, None),
    ]


class TestMavenCoordinates(object):
    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str',
                              'to_str_omit_version', 'to_repo_url'),
                             example_coordinates)
    def test_from_str(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version,
                      to_repo_url):
        from_strings = from_str if isinstance(from_str, list) else [from_str]
        for fstr in from_strings:
            if is_from_str_ok:
                assert MavenCoordinates.from_str(fstr) == coords
            else:
                with pytest.raises(ValueError):
                    MavenCoordinates.from_str(fstr)

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str',
                             'to_str_omit_version', 'to_repo_url'), example_coordinates)
    def test_to_str(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version,
                    to_repo_url):
        if to_str:
            assert coords.to_str() == to_str
        if to_str_omit_version:
            assert coords.to_str(omit_version=True) == to_str_omit_version

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str',
                              'to_str_omit_version', 'to_repo_url'), example_coordinates)
    def test_to_repo_url(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version,
                         to_repo_url):
        if to_repo_url:
            assert coords.to_repo_url() == to_repo_url


class TestGetAnityaProject(object):
    def test_basic(self):
        resp = flexmock(json=lambda: {'a': 'b'},
                        raise_for_status=lambda: None)
        url = configuration.ANITYA_URL + '/api/by_ecosystem/foo/bar'
        flexmock(requests).should_receive('get').with_args(url).and_return(resp)
        assert get_latest_upstream_details('foo', 'bar') == {'a': 'b'}

    def test_bad_status(self):
        resp = flexmock(json=lambda: {'a': 'b'})
        resp.should_receive('raise_for_status').and_raise(Exception())
        url = configuration.ANITYA_URL + '/api/by_ecosystem/foo/bar'
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

        engine = create_engine(configuration.POSTGRES_CONNECTION)
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
        'http://github.com/user/repo/something',
    ])
    def test_parse_gh_repo_nok(self, url):
        assert parse_gh_repo(url) is None


class TestUrl2GitRepo(object):
    @pytest.mark.parametrize('url,expected_result', [
        ('git@github.com:foo/bar', 'https://github.com/foo/bar'),
        ('git@github.com:foo/bar.git', 'https://github.com/foo/bar.git'),
        ('https://github.com/foo/bar.git', 'https://github.com/foo/bar.git'),
        ('git+https://github.com/foo/bar.git', 'https://github.com/foo/bar.git')
    ])
    def test_url2git_repo_ok(self, url, expected_result):
        assert url2git_repo(url) == expected_result

    @pytest.mark.parametrize('url', [
        'git@github.com/foo/bar'
    ])
    def test_url2git_repo_nok(self, url):
        with pytest.raises(ValueError):
            url2git_repo(url)
