"""Core classes for working with git, archives and downloading of artifacts."""
import glob
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import os
import requests
import shutil
from git2json import run_git_log
from git2json.parser import parse_commits
from re import compile as re_compile

from f8a_worker.defaults import configuration
from f8a_worker.enums import EcosystemBackend
from f8a_worker.errors import TaskError, NotABugTaskError
from f8a_worker.utils import cwd, TimedCommand, compute_digest, MavenCoordinates, url2git_repo

logger = logging.getLogger(__name__)


class Git(object):
    """Provide util git functions for git repository located at local path."""

    def __init__(self, path):
        """Initialize."""
        self.repo_path = path

    @staticmethod
    def config():
        """Configure git."""
        user_name = configuration.GIT_USER_NAME
        user_email = configuration.GIT_USER_EMAIL
        if not TimedCommand.get_command_output(["git", "config", "--get", "user.name"]):
            TimedCommand.get_command_output(["git", "config", "--global", "user.name", user_name])
        if not TimedCommand.get_command_output(["git", "config", "--get", "user.email"]):
            TimedCommand.get_command_output(["git", "config", "--global", "user.email", user_email])
        # Use 'true' as external program to ask for credentials, i.e. don't ask
        # Better would be GIT_TERMINAL_PROMPT=0, but that requires git >= 2.3
        TimedCommand.get_command_output(["git", "config", "--global", "core.askpass",
                                         "/usr/bin/true"])

    @classmethod
    def clone(cls, url, path, timeout=300, depth=None, branch=None, single_branch=False):
        """Clone repository provided as url to specific path.

        :param url: str
        :param path: str
        :param timeout: int
        :param depth: str
        :param branch: str
        :param single_branch: bool, only checkout single branch
        :return: instance of Git()
        """
        orig_url = url
        # git clone doesn't understand urls starting with: git+ssh, git+http, git+https
        url = url2git_repo(url)

        orig_path = path
        path = Path(path)
        mode = 0
        if path.is_dir():
            mode = path.stat().st_mode

        cmd = ["git", "clone", url, orig_path]
        if depth is not None:
            cmd.extend(["--depth", depth])
        if branch is not None:
            cmd.extend(["--branch", branch])
        if single_branch:
            cmd.extend(["--single-branch"])
        try:
            cls.config()
            TimedCommand.get_command_output(cmd, graceful=False, timeout=timeout)
        except TaskError as exc:
            if not path.is_dir() and mode:
                # 'git clone repo dir/' deletes (no way to turn this off) dir/ if cloning fails.
                # This might confuse caller of this method, so we recreate the dir on error here.
                try:
                    path.mkdir(mode)
                except OSError:
                    logger.error("Unable to re-create dir: %s", str(path))
            raise TaskError("Unable to clone: %s" % orig_url) from exc
        return cls(path=orig_path)

    @classmethod
    def create_git(cls, path):
        """Initialize new git repository at path.

        :param path: str
        :return: instance of Git()
        """
        cls.config()
        TimedCommand.get_command_output(["git", "init", path], graceful=False)
        return cls(path=path)

    def commit(self, message='blank'):
        """Commit git repository.

        :param message: str, commit message
        """
        # --git-dir is #$%^&&
        # http://stackoverflow.com/questions/1386291/git-git-dir-not-working-as-expected
        with cwd(self.repo_path):
            TimedCommand.get_command_output(["git", "commit", "-m", message], graceful=False)

    def log(self):
        """Parse git log history and return its content in a dictionary.

        :return: a dict representing git log entries
        """
        return list(parse_commits(run_git_log(os.path.join(self.repo_path, '.git'))))

    def rev_parse(self, args=None):
        """Run git rev-parse.

        :param args: arguments to pass to `git rev-parse`
        :return: [str], output from `git rev-parse`
        """
        cmd = ["git", "rev-parse"]
        if args:
            cmd.extend(args)

        with cwd(self.repo_path):
            return TimedCommand.get_command_output(cmd, graceful=False)

    def add(self, path):
        """Add path to index.

        :param path: str
        """
        with cwd(self.repo_path):
            TimedCommand.get_command_output(["git", "add", path], graceful=False)

    def add_and_commit_everything(self, message="blank"):
        """Add and commit.

        git add .
        git commit -m everything

        :param message: str, commit message
        """
        # first we need to remove any .git dirs/files from the archive, they could contain
        #  directions that would break adding (e.g. Flask 0.10 contains .git with gitpath
        #  pointing to Mitsuhiko's home dir)
        TimedCommand.get_command_output(['find', self.repo_path, '-mindepth', '2', '-name', '.git',
                                         '-exec', 'rm', '-rf', '{}', ';'])
        # add everything
        self.add(self.repo_path)
        self.commit(message=message)

    def archive(self, basename, basedir=None, sub_path=None, format="tar.gz"):
        """Create an archive; simply calls `git archive`.

        :param basename: str, name of the resulting archive, without file extension (suffix)
        :param basedir: str, path to a directory where to store the resulting archive
        :param sub_path: str, only add files found under this path to the archive;
                          default: add all files from the repository (.git/ is always excluded)
        :param format: str, format of the resulting archive, default: 'tar.gz'
        :return: str, filename
        """
        filename = os.path.join(basedir or "", basename + "." + format)
        with cwd(self.repo_path):
            cmd = ["git", "archive",
                   "--format={}".format(format),
                   "--output={}".format(filename),
                   "HEAD"]
            if sub_path:
                cmd.append(sub_path)
            TimedCommand.get_command_output(cmd)

        return filename

    def reset(self, revision, hard=False):
        """Run 'git reset'."""
        cmd = ["git", "reset", revision]
        if hard:
            cmd.extend(["--hard"])
        with cwd(self.repo_path):
            TimedCommand.get_command_output(cmd, graceful=False)

    @staticmethod
    def ls_remote(repository, refs=None, args=None):
        """Get output of `git ls-remote <args> <repo> <refs>` command.

        :param repository: str, remote git repository
        :param refs: list, list of git references
        :param args: list, list of additional arguments for the command
        :return: command output
        """
        cmd = ["git", "ls-remote"]
        if args:
            cmd.extend(args)

        cmd.append(repository)

        if refs:
            cmd.extend(refs)

        return TimedCommand.get_command_output(cmd, graceful=False)


class Archive(object):
    """Extract different kind of archives."""

    TarMatcher = re_compile(r'\.tar\..{1,3}$')

    @staticmethod
    def extract(target, dest):
        """Detect archive type and extracts it."""
        tar = Archive.TarMatcher.search(target)
        if target.endswith(('.zip', '.whl', '.egg', '.jar', '.war', '.aar', '.nupkg')):
            return Archive.extract_zip(target, dest)
        elif target.endswith('.gem'):
            return Archive.extract_gem(target, dest)
        elif tar or target.endswith(('.tgz', '.bz2')):
            return Archive.extract_tar(target, dest)
        else:
            raise ValueError('Unknown archive for {0}'.format(target))

    @staticmethod
    def zip_file(file, archive, junk_paths=False):
        """Zip file/dir with system 'zip' command."""
        command = ['zip', '-r', archive, file]
        if junk_paths:
            # Store just the name of a saved file (junk the path), not directory names.
            # By default, zip will store the full path (relative to the current directory).
            command.extend(['--junk-paths'])
        TimedCommand.get_command_output(command, graceful=False)

    @staticmethod
    def extract_zip(target, dest, mkdest=False):
        """Extract target zip archive into dest using system 'unzip' command."""
        if mkdest:
            try:
                os.mkdir(dest, mode=0o775)
            except FileExistsError:
                pass
        # -o: overwrite existing files without prompting
        TimedCommand.get_command_output(['unzip', '-q', '-o', '-d', dest, target])
        # Fix possibly wrong permissions in zip files that would prevent us from deleting files.
        TimedCommand.get_command_output(['chmod', '-R', 'u+rwX,g+rwX', dest])

    @staticmethod
    def extract_tar(target, dest):
        """Extract target tarball into dest using system 'tar' command."""
        TimedCommand.get_command_output(['tar', "--delay-directory-restore", '-xf', target, '-C',
                                         dest])

    @staticmethod
    def fix_permissions(target):
        """Fix extracted folder permissions, so it will be readable for user."""
        TimedCommand.get_command_output(['chmod', "-R", "u+rwx", target])

    @staticmethod
    def extract_gem(target, dest):
        """Extract target gem and gemspec.

        Gem into $dest/sources
        Gemspec (renamed to rubygems-metadata.yaml) into $dest/metadata/
        """
        sources = os.path.join(dest, 'sources')
        metadata = os.path.join(dest, 'metadata')
        TimedCommand.get_command_output(['mkdir', '-p', sources, metadata])
        TimedCommand.get_command_output(['gem', 'unpack', target, '--target', sources])
        with cwd(metadata):
            # --spec ignores --target, so we need to cwd
            TimedCommand.get_command_output(['gem', 'unpack', target, '--spec'])
            metadatayaml = glob.glob('*.gemspec').pop()
            os.rename(metadatayaml, 'rubygems-metadata.yaml')


class IndianaJones(object):
    """Legendary class for retrieving of artifacts."""

    @staticmethod
    def download_file(url, target_dir=None, name=None):
        """Download file from url."""
        if url.endswith('/'):
            url = url[:-1]
        local_filename = name or url.split('/')[-1]

        logger.debug("fetching artifact from: %s", url)
        if target_dir:
            local_filename = os.path.join(target_dir, local_filename)

        r = requests.get(url, stream=True)
        if r.status_code == 404:
            logger.error("unable to download: %s", url)
            return None

        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        logger.debug("artifact location: %s", local_filename)

        return local_filename

    @staticmethod
    def get_revision(target_directory):
        """Get digest of last commit."""
        with cwd(target_directory):
            return TimedCommand.get_command_output(['git', 'rev-parse', 'HEAD'],
                                                   graceful=False).pop()

    @staticmethod
    def fetch_maven_artifact(ecosystem, name, version, target_dir):
        """Fetch maven artifact from maven.org."""
        git = Git.create_git(target_dir)
        artifact_coords = MavenCoordinates.from_str(name)
        if not version:
            raise ValueError("No version provided for '%s'" % artifact_coords.to_str())
        artifact_coords.version = version
        if not artifact_coords.is_valid():
            raise NotABugTaskError("Invalid Maven coordinates: {a}".format(
                a=artifact_coords.to_str()))

        maven_url = ecosystem.fetch_url
        artifact_url = urljoin(maven_url, artifact_coords.to_repo_url())
        local_filepath = IndianaJones.download_file(artifact_url, target_dir)
        if local_filepath is None:
            raise NotABugTaskError("Unable to download: %s" % artifact_url)

        local_filename = os.path.split(local_filepath)[1]
        artifact_path = os.path.join(target_dir, local_filename)
        digest = compute_digest(artifact_path)
        if artifact_coords.packaging != 'pom':
            Archive.extract(artifact_path, target_dir)
            if artifact_coords.packaging == 'aar':
                # 'aar' archive contains classes.jar, extract it too into target_dir
                classes_jar_path = os.path.join(target_dir, "classes.jar")
                if os.path.isfile(classes_jar_path):
                    Archive.extract(classes_jar_path, target_dir)
                    os.remove(classes_jar_path)

        git.add_and_commit_everything()
        return digest, artifact_path

    @staticmethod
    def fetch_npm_artifact(ecosystem, name, version, target_dir):
        """Fetch npm artifact using system 'npm' tool."""
        git = Git.create_git(target_dir)

        npm_cmd = ['npm', '--registry', ecosystem.fetch_url]

        # $ npm config get cache
        # /root/.npm
        cache_path = TimedCommand.get_command_output(npm_cmd + ['config', 'get', 'cache'],
                                                     graceful=False).pop()

        # add package to cache:
        # /root/.npm/express/
        # └── 4.13.4
        #      ├── package
        #      │   ├── History.md
        #      │   ├── index.js
        #      │   ├── lib
        #      │   ├── LICENSE
        #      │   ├── package.json
        #      │   └── Readme.md
        #      └── package.tgz
        # 3 directories, 6 files
        name_ver = name

        try:
            # importing here to avoid circular dependency
            from f8a_worker.solver import NpmReleasesFetcher

            version_list = NpmReleasesFetcher(ecosystem).fetch_releases(name_ver)[1]
            if version not in version_list:
                raise NotABugTaskError("Provided version is not supported '%s'" % name)
            else:
                name_ver = "{}@{}".format(name, version)
        except ValueError as e:
            raise NotABugTaskError(
                'No versions for package NPM package {p} ({e})'.format(p=name, e=str(e))
            )

        # make sure the artifact is not in the cache yet
        TimedCommand.get_command_output(npm_cmd + ['cache', 'clean', name], graceful=False)
        logger.info("downloading npm module %s", name_ver)
        cmd = npm_cmd + ['cache', 'add', name_ver]
        TimedCommand.get_command_output(cmd, graceful=False)

        # copy tarball to workpath
        tarball_name = "package.tgz"
        glob_path = os.path.join(cache_path, name, "*")
        cache_abs_path = os.path.abspath(glob.glob(glob_path).pop())
        artifact_path = os.path.join(cache_abs_path, tarball_name)
        logger.debug("[cache] tarball path = %s", artifact_path)
        artifact_path = shutil.copy(artifact_path, target_dir)

        logger.debug("[workdir] tarball path = %s", artifact_path)
        # Prior to npm-2.x.x (Fedora 24)
        # npm client was repackaging modules on download. It modified file permissions inside
        # package.tgz so they matched UID/GID of a user running npm command. Therefore its
        # digest was different then of a tarball downloaded directly from registry.npmjs.org.
        digest = compute_digest(artifact_path)
        Archive.extract(artifact_path, target_dir)
        Archive.fix_permissions(os.path.join(cache_abs_path, 'package'))

        # copy package/package.json over the extracted one,
        # because it contains (since npm >= 2.x.x) more information.
        npm_package_json = os.path.join(cache_abs_path, 'package', 'package.json')
        shutil.copy(npm_package_json, target_dir)
        # copy package/npm-shrinkwrap.json to target_dir
        npm_shrinkwrap_json = os.path.join(target_dir, 'package', 'npm-shrinkwrap.json')
        if os.path.isfile(npm_shrinkwrap_json):
            shutil.copy(npm_shrinkwrap_json, target_dir)
        git.add_and_commit_everything()
        return digest, artifact_path

    @staticmethod
    def fetch_nuget_artifact(ecosystem, name, version, target_dir):
        """Fetch nuget artifact from nuget.org."""
        git = Git.create_git(target_dir)
        nuget_url = ecosystem.fetch_url
        file_url = '{url}{name}.{version}.nupkg'.format(url=nuget_url,
                                                        name=name.lower(),
                                                        version=version.lower())
        local_filename = IndianaJones.download_file(file_url, target_dir)
        if local_filename is None:
            raise NotABugTaskError("Unable to download: %s" % file_url)
        artifact_path = os.path.join(target_dir, local_filename)
        digest = compute_digest(artifact_path)
        Archive.extract(artifact_path, target_dir)
        git.add_and_commit_everything()
        return digest, artifact_path

    @staticmethod
    def fetch_pypi_artifact(ecosystem, name, version, target_dir):
        """Fetch Pypi artifact."""
        git = Git.create_git(target_dir)
        pypi_url = ecosystem.fetch_url

        # NOTE: we can't download Python packages via pip, because it runs setup.py
        #  even with `pip download`. Therefore we could always get syntax errors
        #  because of older/newer syntax.
        res = requests.get(urljoin(pypi_url, '{n}/json'.format(n=name)))

        if res.status_code != 200:
            raise NotABugTaskError(
                "Unable to fetch information about {n} from PyPI (status code={s})".format(
                    n=name, s=res.status_code
                )
            )

        if not version:
            version = res.json()['info']['version']
        release_files = res.json().get('releases', {}).get(version, [])
        if not release_files:
            raise NotABugTaskError("No release files for version %s" % version)

        # sort releases by order in which we'd like to download:
        #  1) sdist
        #  2) wheels
        #  3) eggs
        #  4) anything else (creepy stuff)
        def release_key(rel):
            return {'sdist': 0, 'bdist_wheel': 1, 'bdist_egg': 2}.get(rel['packagetype'], 3)

        release_files = list(sorted(release_files, key=release_key))
        file_url = release_files[0]['url']
        local_filename = IndianaJones.download_file(file_url, target_dir)
        if local_filename is None:
            raise NotABugTaskError("Unable to download: %s" % file_url)
        artifact_path = os.path.join(target_dir, local_filename)
        digest = compute_digest(artifact_path)
        Archive.extract(artifact_path, target_dir)
        git.add_and_commit_everything()
        return digest, artifact_path

    @staticmethod
    def fetch_rubygems_artifact(ecosystem, name, version, target_dir):
        """Fetch rubygems artifact using 'gem fetch' command."""
        git = Git.create_git(target_dir)
        logger.info("downloading rubygems package %s-%s", name, version)
        version_arg = []
        if version:
            version_arg = ['--version', version]
        gem_command = ['gem', 'fetch', name]
        gem_command.extend(version_arg)
        with cwd(target_dir):
            TimedCommand.get_command_output(gem_command, graceful=False)

        if not version:
            # if version is None we need to glob for the version that was downloaded
            artifact_path = os.path.abspath(glob.glob(os.path.join(
                target_dir, name + '*')).pop())
        else:
            artifact_path = os.path.join(target_dir, '{n}-{v}.gem'.format(
                n=name, v=version))

        digest = compute_digest(artifact_path)
        Archive.extract(artifact_path, target_dir)
        git.add_and_commit_everything()
        return digest, artifact_path

    @staticmethod
    def fetch_scm_artifact(name, version, target_dir):
        """Fetch go artifact using 'go get' command."""
        env = dict(os.environ)
        env['GOPATH'] = target_dir
        Git.config()
        try:
            TimedCommand.get_command_output(
                ['go', 'get', '-d', name],
                timeout=300,
                env=env,
                graceful=False
            )
        except TaskError:
            raise NotABugTaskError('Unable to go-get {n}'.format(n=name))
        package_dir = os.path.join(target_dir, 'src', name)
        with cwd(package_dir):
            git = Git(package_dir)
            git.reset(version, hard=True)
            artifact_filename = git.archive(version)
            artifact_path = os.path.join(package_dir, artifact_filename)
            digest = compute_digest(artifact_path)
            return digest, artifact_path

    @staticmethod
    def fetch_artifact(ecosystem=None,
                       artifact=None,
                       version=None,
                       target_dir='.'):
        """Download artifact from registry and process it.

        :return: tuple: (digest, artifact_path)
        """
        parsed = urlparse(artifact)
        digest = None
        artifact_path = None

        if ecosystem.is_backed_by(EcosystemBackend.pypi):
            digest, artifact_path = IndianaJones.fetch_pypi_artifact(
                ecosystem, artifact, version, target_dir
            )
        elif ecosystem.is_backed_by(EcosystemBackend.npm):
            digest, artifact_path = IndianaJones.fetch_npm_artifact(
                ecosystem, artifact, version, target_dir
            )
        elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
            digest, artifact_path = IndianaJones.fetch_rubygems_artifact(
                ecosystem, artifact, version, target_dir
            )
        elif ecosystem.is_backed_by(EcosystemBackend.maven):
            digest, artifact_path = IndianaJones.fetch_maven_artifact(
                ecosystem, artifact, version, target_dir
            )
        elif ecosystem.is_backed_by(EcosystemBackend.nuget):
            digest, artifact_path = IndianaJones.fetch_nuget_artifact(
                ecosystem, artifact, version, target_dir
            )
        elif ecosystem.is_backed_by(EcosystemBackend.scm):
            digest, artifact_path = IndianaJones.fetch_scm_artifact(
                artifact, version, target_dir
            )
        elif parsed:
            if parsed[0] == 'git' or parsed[2].endswith('.git'):
                git = Git.clone(artifact, target_dir)
                digest = IndianaJones.get_revision(target_dir)
                artifact_path = git.archive(artifact)

        return digest, artifact_path
