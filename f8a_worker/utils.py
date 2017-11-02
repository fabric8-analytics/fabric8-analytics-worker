import getpass
import json
import logging
import datetime
import tempfile
import shutil
import signal
from os import path as os_path, walk, getcwd, chdir, environ as os_environ, killpg, getpgid
from threading import Thread
from subprocess import Popen, PIPE, check_output, CalledProcessError, TimeoutExpired
from traceback import format_exc
from shlex import split
from queue import Queue, Empty
from contextlib import contextmanager
from urllib.parse import unquote
import requests
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import desc

from f8a_worker.defaults import configuration
from f8a_worker.errors import TaskError
from f8a_worker.models import (Analysis, Ecosystem, Package, Version,
                               PackageGHUsage, ComponentGHUsage, DownstreamMap)

from selinon import StoragePool

logger = logging.getLogger(__name__)


def get_package_dependents_count(ecosystem_backend, package, db_session=None):
    """Get number of GitHub projects dependent on the `package`.

    :param ecosystem_backend: str, Ecosystem backend from `f8a_worker.enums.EcosystemBackend`
    :param package: str, Package name
    :param db_session: obj, Database session to use for querying
    :return: number of dependent projects, or -1 if the information is not available
    """
    if not db_session:
        storage = StoragePool.get_connected_storage("BayesianPostgres")
        db_session = storage.session

    try:
        count = db_session.query(PackageGHUsage.count).filter(PackageGHUsage.name == package) \
                          .filter(PackageGHUsage.ecosystem_backend == ecosystem_backend) \
                          .order_by(desc(PackageGHUsage.timestamp)) \
                          .first()
    except SQLAlchemyError:
        db_session.rollback()
        raise

    if count:
        return count[0]
    return -1


def get_dependents_count(ecosystem_backend, package, version, db_session=None):
    """Get number of GitHub projects dependent on given (package, version).

    :param ecosystem_backend: str, Ecosystem backend from `f8a_worker.enums.EcosystemBackend`
    :param package: str, Package name
    :param version: str, Package version
    :param db_session: obj, Database session to use for querying
    :return: number of dependent projects, or -1 if the information is not available
    """
    if not db_session:
        storage = StoragePool.get_connected_storage("BayesianPostgres")
        db_session = storage.session

    try:
        count = db_session.query(ComponentGHUsage.count) \
                          .filter(ComponentGHUsage.name == package) \
                          .filter(ComponentGHUsage.version == version) \
                          .filter(ComponentGHUsage.ecosystem_backend == ecosystem_backend) \
                          .order_by(desc(ComponentGHUsage.timestamp)) \
                          .first()
    except SQLAlchemyError:
        db_session.rollback()
        raise

    if count:
        return count[0]
    return -1


def get_latest_analysis(ecosystem, package, version, db_session=None):
    """ Get latest analysis for the given EPV"""
    if not db_session:
        storage = StoragePool.get_connected_storage("BayesianPostgres")
        db_session = storage.session

    try:
        return db_session.query(Analysis).\
            filter(Ecosystem.name == ecosystem).\
            filter(Package.name == package).\
            filter(Version.identifier == version).\
            order_by(Analysis.started_at.desc()).\
            first()
    except SQLAlchemyError:
        db_session.rollback()
        raise


def get_component_percentile_rank(ecosystem_backend, package, version, db_session=None):
    """Get component's percentile rank.

    :param ecosystem_backend: str, Ecosystem backend from `f8a_worker.enums.EcosystemBackend`
    :param package: str, Package name
    :param version: str, Package version
    :param db_session: obj, Database session to use for querying
    :return: component's percentile rank, or -1 if the information is not available
    """

    if not db_session:
        storage = StoragePool.get_connected_storage("BayesianPostgres")
        db_session = storage.session

    try:
        rank = db_session.query(ComponentGHUsage.percentile_rank) \
            .filter(ComponentGHUsage.name == package) \
            .filter(ComponentGHUsage.version == version) \
            .filter(ComponentGHUsage.ecosystem_backend == ecosystem_backend) \
            .order_by(desc(ComponentGHUsage.timestamp)) \
            .first()
    except SQLAlchemyError:
        db_session.rollback()
        raise

    if rank:
        return rank[0]
    return 0


@contextmanager
def cwd(target):
    "Manage cwd in a pushd/popd fashion"
    curdir = getcwd()
    chdir(target)
    try:
        yield
    finally:
        chdir(curdir)


@contextmanager
def tempdir():
    dirpath = tempfile.mkdtemp()
    try:
        yield dirpath
    finally:
        if os_path.isdir(dirpath):
            shutil.rmtree(dirpath)


@contextmanager
def username():
    """ workaround for failing getpass.getuser()
        http://blog.dscpl.com.au/2015/12/unknown-user-when-running-docker.html
    """
    user = ''
    try:
        user = getpass.getuser()
    except KeyError:
        os_environ['LOGNAME'] = 'f8aworker'

    try:
        yield
    finally:
        if not user:
            del os_environ['LOGNAME']


def assert_not_none(name, value):
    if value is None:
        raise ValueError('Parameter %r is None' % name)


class TimedCommand(object):
    """Execute arbitrary shell command in a timeout-able manner."""

    def __init__(self, command):
        # parse with shlex if not execve friendly
        if isinstance(command, str):
            command = split(command)

        self.command = command

    def run(self, timeout=None, is_json=False, **kwargs):
        """Run the self.command and wait up to given time period for results.

        :param timeout: how long to wait, in seconds, for the command to finish
        before terminating it
        :param is_json: hint whether output of the command is a JSON
        :return: triplet (return code, stdout, stderr), stdout will be a
        dictionary if `is_json` is True
        """
        logger.debug("running command '%s'; timeout '%s'", self.command, timeout)

        # this gets executed in a separate thread
        def target(**kwargs):
            try:
                self.process = Popen(self.command, universal_newlines=True, **kwargs)
                self.output, self.error = self.process.communicate()
                self.status = self.process.returncode
            except Exception:
                self.output = {} if is_json else []
                self.error = format_exc()
                self.status = -1

        # default stdout and stderr
        if 'stdout' not in kwargs:
            kwargs['stdout'] = PIPE
        if 'stderr' not in kwargs:
            kwargs['stderr'] = PIPE
        if 'update_env' in kwargs:
            # make sure we update environment, not override it
            kwargs['env'] = dict(os_environ, **kwargs['update_env'])
            kwargs.pop('update_env')

        # thread
        thread = Thread(target=target, kwargs=kwargs)
        thread.start()
        thread.join(timeout)

        # timeout reached, terminate the thread
        if thread.is_alive():
            logger.error('Command {cmd} timed out after {t} seconds'.format(cmd=self.command,
                                                                            t=timeout))
            # this is tricky - we need to make sure we kill the process with all its subprocesses;
            #  using just kill might create zombie process waiting for subprocesses to finish
            #  and leaving us hanging on thread.join()
            # TODO: we should do the same for get_command_output!
            killpg(getpgid(self.process.pid), signal.SIGKILL)
            thread.join()
            if not self.error:
                self.error = 'Killed by timeout after {t} seconds'.format(t=timeout)
        if self.output:
            if is_json:
                self.output = json.loads(self.output)
            else:
                self.output = [f for f in self.output.split('\n') if f]

        return self.status, self.output, self.error

    @staticmethod
    def get_command_output(args, graceful=True, is_json=False, timeout=300, **kwargs):
        """Wrapper around get_command_output() with implicit timeout of 5 minutes."""
        kwargs['timeout'] = timeout
        return get_command_output(args, graceful, is_json, **kwargs)


def get_command_output(args, graceful=True, is_json=False, **kwargs):
    """
    improved version of subprocess.check_output

    :param graceful: bool, if False, raise Exception when command fails
    :param is_json: bool, if True, return decoded json

    :return: list of strings, output which command emitted
    """
    logger.debug("running command %s", args)
    try:
        # Using universal_newlines mostly for the side-effect of decoding
        # the output as UTF-8 text on Python 3.x
        out = check_output(args, universal_newlines=True, **kwargs)
    except (CalledProcessError, TimeoutExpired) as ex:
        # TODO: we may want to use subprocess.Popen to be able to also print stderr here
        #  (while not mixing it with stdout that is returned if the subprocess succeeds)
        if isinstance(ex, TimeoutExpired):
            logger.warning("command %s timed out:\n%s", args, ex.output)
        elif isinstance(ex, CalledProcessError):
            if ex.returncode == 1 and "no Go files in" in ex.output:  # skip this error
                logger.warning("No Golang source in base path. Command %s ended with %s\n%s",
                               args, ex.returncode, ex.output)
            else:
                logger.warning("command %s ended with %s\n%s", args, ex.returncode, ex.output)
        else:
            logger.warning("command %s ended with %s\n%s", args, ex.returncode, ex.output)

        if not graceful:
            logger.error("exception is fatal")
            raise TaskError("Error during running command %s: %r" % (args, ex.output))
        else:
            logger.debug("Ignoring because graceful flag is set")
        return []
    else:
        if is_json:
            # FIXME: some error handling here would be great
            return json.loads(out)
        else:
            return [f for f in out.split('\n') if f]  # py2 & 3 compat


def get_all_files_from(target, path_filter=None, file_filter=None):
    "Enumerate all files in target directory, can be filtered with custom delegates"
    for root, dirs, files in walk(target):
        for file in files:
            joined = os_path.abspath(os_path.join(root, file))

            # filter the list early on
            if path_filter and not path_filter(joined):
                continue

            if file_filter and not file_filter(file):
                continue

            yield joined


def hidden_path_filter(item):
    "Filter out hidden files or files in hidden directories"
    return not any(sub.startswith('.') for sub in item.split(os_path.sep))


def json_serial(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError('Type {t} not serializable'.format(t=type(obj)))


def in_path(directory, path):
    """
    is directory in path?

    :param directory: str
    :param path: str

    :return: True if directory is in path
    """
    return any(directory == x for x in path.split(os_path.sep))


def skip_git_files(path):
    "Git skipping closure of in_path"
    return not in_path('.git', path)


class ThreadPool(object):
    def __init__(self, target, num_workers=10, timeout=3):
        """Initialize `ThreadPool`

        :param target: Function that accepts exactly one argument
        :param num_workers: int, number of worker threads to spawn
        :param timeout: int, maximum number of seconds workers wait for new task
        """
        self.target = target
        self.num_workers = num_workers
        self.timeout = timeout
        self.queue = Queue()
        self._threads = [Thread(target=self._work) for i in range(0, num_workers)]

    def add_task(self, arg):
        """Enqueue a new task.

        :param arg: argument for the `target` that was passed to constructor
        """
        self.queue.put(arg)

    def start(self):
        """Start processing by all threads"""
        [t.start() for t in self._threads]

    def join(self):
        [t.join() for t in self._threads]
        self.queue.join()

    def _work(self):
        while True:
            try:
                arg = self.queue.get(block=True, timeout=self.timeout)
            except Empty:
                break
            try:
                self.target(arg)
            finally:
                self.queue.task_done()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.join()


def compute_digest(target, function='sha256', raise_on_error=False):
    """
    compute digest of a provided file

    :param target: str, file path
    :param function: str, prefix name of the hashing function
    :param raise_on_error: bool, raise an error when computation wasn't successful if set to True
    :returns str or None, computed digest

    `function` requires an executable with matching name on the system (sha256sum, sha1sum etc.)
    """
    function += 'sum'
    # returns e.g.:
    # 65ecde5d025fcf57ceaa32230e2ff884ab204065b86e0e34e609313c7bdc7b47  /etc/passwd
    data = TimedCommand.get_command_output([function, target], graceful=not raise_on_error)
    try:
        return data[0].split(' ')[0].strip()
    except IndexError as exc:
        logger.error("unable to compute digest of %r, likely it doesn't exist or is a directory",
                     target)
        if raise_on_error:
            raise RuntimeError("can't compute digest of %s" % target) from exc


class MavenCoordinates(object):
    """
    Represents Maven coordinates.

    https://maven.apache.org/pom.html#Maven_Coordinates
    """

    _default_packaging = 'jar'

    def __init__(self, groupId, artifactId, version='',
                 classifier='', packaging=None):
        self.groupId = groupId
        self.artifactId = artifactId
        self.classifier = classifier
        self.packaging = packaging or MavenCoordinates._default_packaging
        self.version = version

    def is_valid(self):
        """Checks if the current coordinates are valid."""
        return self.groupId and self.artifactId and self.version and self.packaging

    def to_str(self, omit_version=False):
        """Returns string representation of the coordinates."""
        mvnstr = "{g}:{a}".format(g=self.groupId, a=self.artifactId)
        pack = self.packaging
        if pack == MavenCoordinates._default_packaging:
            pack = ''
        if pack:
            mvnstr += ":{p}".format(p=pack)
        if self.classifier:
            if not pack:
                mvnstr += ':'
            mvnstr += ":{c}".format(c=self.classifier)
        if not self.version or omit_version:
            if self.classifier or pack:
                mvnstr += ':'
        else:
            mvnstr += ":{v}".format(v=self.version)

        return mvnstr

    def to_repo_url(self, ga_only=False):
        """Returns relative path to the artifact in Maven repository."""
        if ga_only:
            return "{g}/{a}".format(g=self.groupId.replace('.', '/'),
                                    a=self.artifactId)

        dir_path = "{g}/{a}/{v}/".format(g=self.groupId.replace('.', '/'),
                                         a=self.artifactId,
                                         v=self.version)
        classifier = "-{c}".format(c=self.classifier) if self.classifier else ''
        filename = "{a}-{v}{c}.{e}".format(a=self.artifactId,
                                           v=self.version,
                                           c=classifier,
                                           e=self.packaging)
        return dir_path + filename

    @staticmethod
    def _parse_string(coordinates_str):
        a = {'groupId': '',
             'artifactId': '',
             'packaging': MavenCoordinates._default_packaging,
             'classifier': '',
             'version': ''}

        ncolons = coordinates_str.count(':')
        if ncolons == 1:
            a['groupId'], a['artifactId'] = coordinates_str.split(':')
        elif ncolons == 2:
            a['groupId'], a['artifactId'], a['version'] = coordinates_str.split(':')
        elif ncolons == 3:
            a['groupId'], a['artifactId'], a['packaging'], a['version'] = coordinates_str.split(':')
        elif ncolons == 4:
            a['groupId'], a['artifactId'], a['packaging'], a['classifier'], a['version'] = \
                coordinates_str.split(':')
        else:
            raise ValueError('Invalid Maven coordinates %s', coordinates_str)

        return a

    def __repr__(self):
        return self.to_str()

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def normalize_str(cls, coordinates_str):
        return cls.from_str(coordinates_str).to_str()

    @classmethod
    def from_str(cls, coordinates_str):
        coordinates = MavenCoordinates._parse_string(coordinates_str)
        return cls(**coordinates)


def get_latest_upstream_details(ecosystem, package):
    """Returns dict representation of Anitya project"""
    url = configuration.ANITYA_URL + '/api/by_ecosystem/{e}/{p}'.\
        format(e=ecosystem, p=package)

    res = requests.get(url)
    res.raise_for_status()
    return res.json()


def safe_get_latest_version(ecosystem, package):
    version = None
    try:
        version = get_latest_upstream_details(ecosystem, package)['versions'][0]
    except (requests.exceptions.RequestException, IndexError) as e:
        logger.warning('Unable to obtain latest version information: %r' % e)
    return version


class DownstreamMapCache(object):
    """ Use Postgres as Redis-like hash map. """
    def __init__(self, session=None):
        if session is not None:
            self.session = session
        else:
            storage = StoragePool.get_connected_storage("BayesianPostgres")
            self.session = storage.session

    def _query(self, key):
        """ Returns None if key is not in DB """
        try:
            return self.session.query(DownstreamMap) \
                               .filter(DownstreamMap.key == key) \
                               .first()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def _update(self, key, value):
        q = self._query(key)
        if q and q.value != value:
            try:
                q.value = value
                self.session.commit()
            except SQLAlchemyError:
                self.session.rollback()
                raise

    def __getitem__(self, key):
        q = self._query(key)
        return q.value if q else None

    def __setitem__(self, key, value):
        mapping = DownstreamMap(key=key, value=value)
        try:
            self.session.add(mapping)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            try:
                self._update(key, value)
            except Exception:
                raise
            else:
                pass


def usage_rank2str(rank):
    """Translates percentile rank to a string representing relative usage of a component."""
    used = 'n/a'
    if rank > 90:
        used = 'very often'
    elif rank > 80:
        used = 'often'
    elif rank > 10:
        used = 'used'
    elif rank > 0:
        used = 'seldom'
    elif rank == 0:
        used = 'not used'
    return used


def parse_gh_repo(potential_url):
    """Since people use a wide variety of URL forms for Github repo referencing,
    we need to cover them all. E.g.:

    1) www.github.com/foo/bar
    2) (same as above, but with ".git" in the end)
    3) (same as the two above, but without "www.")
    # all of the three above, but starting with "http://", "https://", "git://" or "git+https://"
    4) git@github.com:foo/bar
    5) (same as above, but with ".git" in the end)
    6) (same as the two above but with "ssh://" in front or with "git+ssh" instead of "git")

    We return repository name in form `<username>/<reponame>` or `None` if this does not
    seem to be a Github repo (or if someone invented yet another form that we can't parse yet...)

    Notably, the Github repo *must* have exactly username and reponame, nothing else and nothing
    more. E.g. `github.com/<username>/<reponame>/<something>` is *not* recognized.

    Fun, eh?
    """
    if not potential_url:
        return None

    repo_name = None
    # transform 4-6 to a URL-like string, so that we can handle it together with 1-3
    if '@' in potential_url:
        split = potential_url.split('@')
        if len(split) == 2 and split[1].startswith('github.com:'):
            potential_url = 'http://' + split[1].replace('github.com:', 'github.com/')

    # make it parsable by urlparse if it doesn't contain scheme
    if not potential_url.startswith(('http://', 'https://', 'git://', 'git+https://')):
        potential_url = 'http://' + potential_url

    # urlparse should handle it now
    parsed = urlparse(potential_url)
    if parsed.netloc in ['github.com', 'www.github.com'] and \
            parsed.scheme in ['http', 'https', 'git', 'git+https']:
        repo_name = parsed.path
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-len('.git')]

    if repo_name:
        repo_name = repo_name.strip('/')
        if repo_name.count('/') != 1:
            return None

    return repo_name


def url2git_repo(url):
    """Convert URL to git repo URL and force use HTTPS."""
    if url.startswith('git+'):
        return url[len('git+'):]

    if url.startswith('git@'):
        url = url[len('git@'):]
        url = url.split(':')
        if len(url) != 2:
            raise ValueError("Unable to parse git repo URL '%s'" % str(url))
        return 'https://{}/{}'.format(url[0], url[1])

    return url


def case_sensitivity_transform(ecosystem, name):
    """Transform package name to lowercase for ecosystem that are not case sensitive.

    :param ecosystem: name of ecosystem in which the package is sits
    :param name: name of ecosystem
    :return: transformed package name base on ecosystem package case sensitivity
    """
    if ecosystem == 'pypi':
        return name.lower()

    return name


def get_session_retry(retries=3, backoff_factor=0.2, status_forcelist=(404, 500, 502, 504),
                      session=None):
    session = session or requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries,
                  backoff_factor=backoff_factor, status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    return session


def normalize_package_name(ecosystem, name):
    normalized_name = name
    if ecosystem == 'pypi':
        case_sensitivity_transform(ecosystem, name)
    elif ecosystem == 'go':
        # go package name is the host+path part of a URL, thus it can be URL encoded
        normalized_name = unquote(name)
    return normalized_name


def get_user_email(user_profile):
    default_email = 'bayesian@redhat.com'
    if user_profile is not None:
        return user_profile.get('email', default_email)
    else:
        return default_email
