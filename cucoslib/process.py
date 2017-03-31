# This Python file uses the following encoding: utf-8
# ^  https://www.python.org/dev/peps/pep-0263/

import os
import glob
import shutil
import logging
import requests

from re import compile as re_compile
from urllib.parse import urljoin, urlparse

from cucoslib.conf import get_configuration
from cucoslib.enums import EcosystemBackend
from cucoslib.utils import (cwd, TimedCommand, compute_digest,
                            MavenCoordinates, mvn_find_latest_version)

logger = logging.getLogger(__name__)
configuration = get_configuration()

# TODO: Default to True, switch to False if Artifactory is unreachable
#       Alternatively, try-and-fallback on every component download attempt
_USE_ARTIFACTORY = False


class Git(object):
    """ Git process helper """

    def __init__(self, path):
        """
        provide util git functions for git repository located at local path

        :param path: str
        :return:
        """
        self.repo_path = path

    @staticmethod
    def config():
        """
        configure git
        """
        user_name = configuration.git_user_name
        user_email = configuration.git_user_email
        if not TimedCommand.get_command_output(["git", "config", "--get", "user.name"]):
            TimedCommand.get_command_output(["git", "config", "--global", "user.name", user_name])
        if not TimedCommand.get_command_output(["git", "config", "--get", "user.email"]):
            TimedCommand.get_command_output(["git", "config", "--global", "user.email", user_email])

    @classmethod
    def clone(cls, url, path):
        """
        clone repository provided as url to specific path

        :param url: str
        :param path: str
        :return: instance of Git()
        """
        cls.config()
        TimedCommand.get_command_output(["git", "clone", url, path], graceful=False)
        return cls(path=path)

    @classmethod
    def create_git(cls, path):
        """
        initiate new git repository at path

        :param path: str
        :return: instance of Git()
        """
        cls.config()
        TimedCommand.get_command_output(["git", "init", path], graceful=False)
        return cls(path=path)

    def commit(self, message='blank'):
        """
        commit git repository

        :param message: str, commit message
        """
        # --git-dir is #$%^&&
        # http://stackoverflow.com/questions/1386291/git-git-dir-not-working-as-expected
        with cwd(self.repo_path):
            TimedCommand.get_command_output(["git", "commit", "-m", message], graceful=False)

    def add(self, path):
        """
        add path to index

        :param path: str
        """
        with cwd(self.repo_path):
            TimedCommand.get_command_output(["git", "add", path], graceful=False)

    def add_and_commit_everything(self, message="blank"):
        """
        equiv of:

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

    def archive(self, basename):
        suffix = "tar.gz"
        filename = basename + "." + suffix
        TimedCommand.get_command_output(["git", "archive", "--format={}".format(suffix),
                                        "--output={}".format(filename), "HEAD"])
        return filename


class Archive(object):
    "Extract different kind of archives"
    TarMatcher = re_compile('\.tar\..{1,3}$')

    @staticmethod
    def extract(target, dest):
        "Detects archive type and extracts it"
        tar = Archive.TarMatcher.search(target)
        if target.endswith(('.zip', '.whl', '.jar')):
            return Archive.extract_zip(target, dest)
        elif target.endswith('.gem'):
            return Archive.extract_gem(target, dest)
        elif tar or target.endswith(('.tgz', '.bz2')):
            return Archive.extract_tar(target, dest)
        else:
            raise ValueError('Unknown archive for {0}'.format(target))

    @staticmethod
    def zip_file(file, archive):
        TimedCommand.get_command_output(['zip', archive, file])

    @staticmethod
    def extract_zip(target, dest):
        # -o: overwrite existing files without prompting
        TimedCommand.get_command_output(['unzip', '-o', '-d', dest, target])
        # Fix possibly wrong permissions in zip files that would prevent us from deleting files.
        TimedCommand.get_command_output(['chmod', '-R', 'u+rwX,g+rwX', dest])

    @staticmethod
    def extract_tar(target, dest):
        TimedCommand.get_command_output(['tar', 'xf', target, '-C', dest])

    @staticmethod
    def extract_gem(target, dest):
        """
        extract target gem into $dest/sources and
                gemspec (renamed to rubygems-metadata.yaml) into $dest/metadata/
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
    @staticmethod
    def download_file(url, target_dir=None, name=None):
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
        """ Get digest of last commit """
        with cwd(target_directory):
            return TimedCommand.get_command_output(['git', 'rev-parse', 'HEAD'], graceful=False).pop()

    @staticmethod
    def fetch_artifact(ecosystem=None,
                       artifact=None,
                       version=None,
                       target_dir='.'):
        """
        download artifact from registry and process it

        :param ecosystem:
        :param artifact:
        :param version:
        :param target_dir:
        :return: tuple: (digest, artifact_path)
        """
        artifactory_host = configuration.artifactory_host
        artifactory_port = configuration.artifactory_port

        artifactory_maven = 'http://%s:%s/artifactory/libs-release/' % \
                            (artifactory_host, artifactory_port)
        artifactory_pypi = 'http://%s:%s/artifactory/api/pypi/pypi/simple/' % \
                           (artifactory_host, artifactory_port)
        artifactory_npm = 'http://%s:%s/artifactory/api/npm/npm/' % \
                          (artifactory_host, artifactory_port)
        artifactory_rubygems = 'http://%s:%s/artifactory/api/gems/gems/' % \
                               (artifactory_host, artifactory_port)

        parsed = urlparse(artifact)
        digest = None
        artifact_path = None

        if ecosystem.is_backed_by(EcosystemBackend.pypi):
            git = Git.create_git(target_dir)
            # NOTE: we can't download Python packages via pip, because it runs setup.py
            #  even with `pip download`. Therefore we could always get syntax errors
            #  because of older/newer syntax.
            res = requests.get('https://pypi.python.org/pypi/{a}/json'.format(a=artifact))
            res.raise_for_status()
            if not version:
                version = res.json()['info']['version']
            release_files = res.json()['releases'][version]
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
            artifact_path = os.path.join(target_dir, local_filename)
            digest = compute_digest(artifact_path)
            Archive.extract(artifact_path, target_dir)
            git.add_and_commit_everything()
        elif ecosystem.is_backed_by(EcosystemBackend.npm):
            git = Git.create_git(target_dir)

            # $ npm config get cache
            # /root/.npm
            cache_path = TimedCommand.get_command_output(['npm', 'config', 'get', 'cache'], graceful=False).pop()

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
            name_ver = artifact
            if version:
                name_ver = "{}@{}".format(artifact, version)
            # make sure the artifact is not in the cache yet
            TimedCommand.get_command_output(['npm', 'cache', 'clean', artifact], graceful=False)
            logger.info("downloading npm module %s", name_ver)
            npm_command = ['npm', 'cache', 'add']
            if _USE_ARTIFACTORY:
                npm_command.extend(['--registry', artifactory_npm])
            npm_command.append(name_ver)
            TimedCommand.get_command_output(npm_command, graceful=False)

            # copy tarball to workpath
            tarball_name = "package.tgz"
            glob_path = os.path.join(cache_path, artifact, "*")
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

            # copy package/package.json over the extracted one,
            # because it contains (since npm >= 2.x.x) more information.
            npm_package_json = os.path.join(cache_abs_path, 'package', 'package.json')
            shutil.copy(npm_package_json, target_dir)
            # copy package/npm-shrinkwrap.json to target_dir
            npm_shrinkwrap_json = os.path.join(target_dir, 'package', 'npm-shrinkwrap.json')
            if os.path.isfile(npm_shrinkwrap_json):
                shutil.copy(npm_shrinkwrap_json, target_dir)
            git.add_and_commit_everything()
        elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
            git = Git.create_git(target_dir)
            logger.info("downloading rubygems package %s-%s", artifact, version)
            version_arg = []
            if version:
                version_arg = ['--version', version]
            gem_command = ['gem', 'fetch']
            if _USE_ARTIFACTORY:
                gem_command.extend(['--source', artifactory_rubygems])
            gem_command.append(artifact)
            gem_command.extend(version_arg)
            with cwd(target_dir):
                TimedCommand.get_command_output(gem_command, graceful=False)

            if not version:
                # if version is None we need to glob for the version that was downloaded
                artifact_path = os.path.abspath(glob.glob(os.path.join(target_dir, artifact + '*')).pop())
            else:
                artifact_path = os.path.join(target_dir, '{n}-{v}.gem'.format(n=artifact, v=version))

            digest = compute_digest(artifact_path)
            Archive.extract(artifact_path, target_dir)
            git.add_and_commit_everything()
        elif ecosystem.is_backed_by(EcosystemBackend.maven):
            git = Git.create_git(target_dir)
            artifact_coords = MavenCoordinates.from_str(artifact)
            if _USE_ARTIFACTORY:
                maven_url = artifactory_maven
            else:
                # lxml can't handle HTTPS URLs
                maven_url = "http://repo1.maven.org/maven2/"
            if not version:
                version = mvn_find_latest_version(maven_url, artifact_coords)
            artifact_coords.version = version
            logger.info("downloading maven package %s", artifact_coords.to_str())

            if not artifact_coords.is_valid():
                raise ValueError("Invalid Maven coordinates: {a}".format(a=artifact_coords.to_str()))

            artifact_url = urljoin(maven_url, artifact_coords.to_repo_url())
            local_filename = IndianaJones.download_file(artifact_url, target_dir)
            if local_filename is None:
                raise RuntimeError("Unable to download: %s" % artifact_url)
            artifact_path = os.path.join(target_dir,
                                         os.path.split(artifact_coords.to_repo_url())[1])
            digest = compute_digest(artifact_path)
            if artifact_coords.packaging != 'pom':
                Archive.extract(artifact_path, target_dir)
            git.add_and_commit_everything()
        elif ecosystem.is_backed_by(EcosystemBackend.scm):
            git = Git.clone(artifact, target_dir)
            digest = IndianaJones.get_revision(target_dir)
            artifact_path = git.archive(artifact)
        elif parsed:
            if parsed[0] == 'git' or parsed[2].endswith('.git'):
                git = Git.clone(artifact, target_dir)
                digest = IndianaJones.get_revision(target_dir)
                artifact_path = git.archive(artifact)

        return digest, artifact_path
