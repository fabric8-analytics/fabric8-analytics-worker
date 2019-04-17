"""Tests covering code in utils.py."""

import errno
import itertools
from pathlib import Path
import pytest
from sqlalchemy.ext.declarative import declarative_base

from f8a_worker.errors import TaskError
from f8a_worker.utils import (
    get_all_files_from,
    hidden_path_filter,
    skip_git_files,
    ThreadPool,
    MavenCoordinates,
    compute_digest,
    parse_gh_repo,
    url2git_repo,
    normalize_package_name
)

Base = declarative_base()


class TestUtilFunctions(object):
    """Test functions from utils.py."""

    def setup_method(self, method):
        """Set up any state tied to the execution of the given method in a class."""
        assert method

    def teardown_method(self, method):
        """Teardown any state that was previously setup with a setup_method call."""
        assert method

    def test_get_all_files_from(self, tmpdir):
        """Test get_all_files_from()."""
        test_dir = Path(str(tmpdir)).resolve()

        def touch_file(path):
            try:
                path.parent.mkdir(parents=True)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    # was created in previous iteration
                    pass
            path.touch()

        py_files = {
            str(test_dir / 'test_path/file.py'),
            str(test_dir / 'test_path/some.py')
        }
        test_files = {
            str(test_dir / 'test_path/test')
        }
        hidden_files = {
            str(test_dir / 'test_path/.hidden')
        }
        git_files = {
            str(test_dir / 'test_path/.git/object')
        }
        all_files = set(itertools.chain(py_files, test_files, hidden_files, git_files))
        for f in all_files:
            touch_file(Path(f))

        test_dir = str(test_dir)
        assert set(get_all_files_from(test_dir)) == all_files
        assert set(get_all_files_from(test_dir, path_filter=skip_git_files)) == \
            set(itertools.chain(py_files, test_files, hidden_files))
        assert set(get_all_files_from(test_dir, file_filter=lambda x: x.endswith('.py'))) == \
            py_files
        assert set(get_all_files_from(test_dir, path_filter=hidden_path_filter)) == \
            set(itertools.chain(py_files, test_files))

    def test_compute_digest(self):
        """Test compute_digest()."""
        assert compute_digest("/etc/os-release")
        with pytest.raises(TaskError):
            assert compute_digest("/", raise_on_error=True)
        assert compute_digest("/") is None


class TestThreadPool(object):
    """Test ThreadPool class."""

    def test_context_manager(self):
        """Test using ThreadPool as context manager."""
        s = set()

        def foo(x):
            s.add(x)

        original = set(range(0, 10))
        with ThreadPool(foo) as tp:
            for i in original:
                tp.add_task(i)

        assert s == original

    def test_normal_usage(self):
        """Test normal usage."""
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
    """Test MavenCoordinates class."""

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str',
                              'to_str_omit_version', 'to_repo_url'),
                             example_coordinates)
    def test_from_str(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version,
                      to_repo_url):
        """Test MavenCoordinates.from_str()."""
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
        """Test MavenCoordinates.to_str()."""
        if to_str:
            assert coords.to_str() == to_str
        if to_str_omit_version:
            assert coords.to_str(omit_version=True) == to_str_omit_version

    @pytest.mark.parametrize(('coords', 'from_str', 'is_from_str_ok', 'to_str',
                              'to_str_omit_version', 'to_repo_url'), example_coordinates)
    def test_to_repo_url(self, coords, from_str, is_from_str_ok, to_str, to_str_omit_version,
                         to_repo_url):
        """Test MavenCoordinates.to_repo_url()."""
        if to_repo_url:
            assert coords.to_repo_url() == to_repo_url


class TestParseGHRepo:
    """Test parse_gh_repo()."""

    @pytest.mark.parametrize('url', [
        'github.com/foo/bar',
        'github.com/foo/bar.git',
        'www.github.com/foo/bar',
        'http://github.com/foo/bar',
        'https://github.com/foo/bar/something'
        'http://github.com/foo/bar.git',
        'git+https://www.github.com/foo/bar',
        'git@github.com:foo/bar',
        'git@github.com:foo/bar.git',
        'git+ssh@github.com:foo/bar.git',
        'ssh://git@github.com:foo/bar.git',
    ])
    def test_parse_gh_repo_ok(self, url):
        """Test parse_gh_repo()."""
        assert parse_gh_repo(url) == 'foo/bar'

    @pytest.mark.parametrize('url', [
        'gitlab.com/foo/bar',
        'git@gitlab.com:foo/bar.git',
        'https://bitbucket.org/foo/bar',
        'something',
        'something@else',
    ])
    def test_parse_gh_repo_nok(self, url):
        """Test parse_gh_repo()."""
        assert parse_gh_repo(url) is None


class TestUrl2GitRepo(object):
    """Test url2git_repo()."""

    @pytest.mark.parametrize('url,expected_result', [
        ('git@github.com:foo/bar', 'https://github.com/foo/bar'),
        ('git@github.com:foo/bar.git', 'https://github.com/foo/bar.git'),
        ('https://github.com/foo/bar.git', 'https://github.com/foo/bar.git'),
        ('git+https://github.com/foo/bar.git', 'https://github.com/foo/bar.git')
    ])
    def test_url2git_repo_ok(self, url, expected_result):
        """Test url2git_repo()."""
        assert url2git_repo(url) == expected_result

    @pytest.mark.parametrize('url', [
        'git@github.com/foo/bar'
    ])
    def test_url2git_repo_nok(self, url):
        """Test url2git_repo()."""
        with pytest.raises(ValueError):
            url2git_repo(url)


@pytest.mark.parametrize('ecosystem,name,expected_result', [
    ('pypi', 'PyJWT', 'pyjwt'),
    ('pypi', 'Flask_Cache', 'flask-cache'),
    ('pypi', 'Flask-Cache', 'flask-cache'),
    ('maven', 'junit:junit:4.12', 'junit:junit:4.12'),
    ('maven', 'junit:junit:jar:4.12', 'junit:junit:4.12'),
    ('maven', 'junit:junit:jar::4.12', 'junit:junit:4.12'),
    ('maven', 'junit:junit:jar:sources:4.12', 'junit:junit::sources:4.12'),
    ('maven', 'junit:junit', 'junit:junit'),
    ('maven', 'junit:junit:', 'junit:junit'),
    ('maven', 'junit:junit::', 'junit:junit'),
    ('maven', 'junit:junit:::4.12', 'junit:junit:4.12'),
    ('npm', 'fs-extra', 'fs-extra'),
    ('npm', 'JSONstream', 'JSONstream'),
    ('go', 'github.com%2Fmitchellh%2Fgo-homedir', 'github.com/mitchellh/go-homedir'),
    ('go', 'github.com/mitchellh/go-homedir', 'github.com/mitchellh/go-homedir'),
])
def test_normalize_package_name(ecosystem, name, expected_result):
    """Test normalize_package_name()."""
    assert normalize_package_name(ecosystem, name) == expected_result
