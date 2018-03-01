"""Tests covering code in process.py."""

import glob
import os
from pathlib import Path
import pytest
import subprocess

from f8a_worker.process import Git, IndianaJones


class TestGit(object):
    """Test Git class."""

    def test_git_add_and_commit_everything_with_dotgit(self, tmpdir):
        """Test Git.add_and_commit_everything()."""
        # if there's a .git file somewhere in the archive, we don't want it to fail adding
        subprocess.check_output(['git', 'init', str(tmpdir)], universal_newlines=True)
        d = os.path.join(str(tmpdir), 'foo')
        os.makedirs(d)
        with open(os.path.join(d, '.git'), 'w') as f:
            f.write('gitdir: /this/doesnt/exist/hehehe')
        # we need at least one normal file for git to commit
        with open(os.path.join(d, 'foo'), 'w'):
            pass
        g = Git.create_git(str(tmpdir))
        g.add_and_commit_everything()


class TestIndianaJones(object):
    """Test IndianaJones class."""

    @pytest.mark.parametrize("name, version, expected_digest", [
        # Prior to npm-2.x.x (Fedora 24)
        # npm client was repackaging modules on download. It modified file permissions inside
        # package.tgz so they matched UID/GID of a user running npm command. Therefore
        # this hash was valid only for user 1000:1000.
        # If the test that checks this fails, it means that the feature is back in npm and we can't
        # rely on the digest of the npm downloaded tarball matching the upstream one.
        # In that case we should probably consider downloading tarballs directly from
        # registry.npmjs.org, because for example AnityaTask relies on this.
        ("abbrev", "1.0.7", "30f6880e415743312a0021a458dd6d26a7211f803a42f1e4a30ebff44d26b7de"),
        ("abbrev", "1.0.4", "8dc0f480571a4a19e74f1abd4f31f6a70f94953d1ccafa16ed1a544a19a6f3a8")
    ])
    def test_fetch_npm_specific(self, tmpdir, npm, name, version, expected_digest):
        """Test fetching of npm artifact."""
        cache_path = Path(subprocess.check_output(["npm", "config", "get", "cache"],
                                                  universal_newlines=True).strip())
        assert cache_path.name == ".npm"
        package_digest, path = IndianaJones.fetch_artifact(npm,
                                                           artifact=name,
                                                           version=version,
                                                           target_dir=str(tmpdir))
        assert len(list((cache_path / name).glob('*'))) == 1,\
            "there should be just one version of the artifact in the NPM cache"
        assert package_digest == expected_digest
        assert Path(path).exists()
        assert (cache_path / name / version).exists()
        assert Path(str(tmpdir / "package.tgz")).exists()

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('six', '1.0.0', 'ca79c14c8cb5e58912d185f0e07ca9c687e232b7c68c4b73bf1c83ef5979333e'),
    ])
    def test_fetch_pypi_specific(self, tmpdir, pypi, name, version, expected_digest):
        """Test fetching of pypi artifact."""
        tmpdir = Path(str(tmpdir))
        digest, path = IndianaJones.fetch_artifact(pypi,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        assert len(list(tmpdir.iterdir())) > 1
        glob_whl_path = next(tmpdir.glob("{}-{}*".format(name, version)))
        assert glob_whl_path.exists()

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('permutation', '0.1.7', 'e715cccaccb8e2d1450fbdda85bbe84963a32e9bf612db278cbb3d6781267638')
    ])
    def test_fetch_rubygems_specific(self, tmpdir, rubygems, name, version, expected_digest):
        """Test fetching of rubygems artifact."""
        digest, path = IndianaJones.fetch_artifact(rubygems,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        path = Path(path)
        assert path.name == "{}-{}.gem".format(name, version)
        assert path.exists()

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('com.rabbitmq:amqp-client', '3.6.1',
         'cb6cdb7de8d37cb1b15b23867435c7dbbeaa1ca4b766f434138a8b9ef131994f'),
    ])
    def test_fetch_maven_specific(self, tmpdir, maven, name, version, expected_digest):
        """Test fetching of maven artifact."""
        digest, path = IndianaJones.fetch_artifact(maven,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        _, artifactId = name.split(':', 1)
        assert digest == expected_digest
        path = Path(path)
        assert path.name == '{}-{}.jar'.format(artifactId, version)
        assert path.exists()

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('NUnit', '3.7.1', 'db714c0a01d8a172e6c378144b1192290263f8c308e8e2baba9c11d9fe165db4'),
    ])
    def test_fetch_nuget_specific(self, tmpdir, nuget, name, version, expected_digest):
        """Test fetching of nuget artifact."""
        digest, path = IndianaJones.fetch_artifact(nuget,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        path = Path(path)
        assert path.name == '{}.{}.nupkg'.format(name.lower(), version)
        assert path.exists()

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('github.com/gorilla/mux', '3f19343c7d9ce75569b952758bd236af94956061',
         '50cc6ce3b58fb23f7f4e5ccf8e24897ba63c628fdc4a52ef4648ecdad7a0a0e9'),
        ('github.com/flynn/flynn/bootstrap', 'v20171027.0',
         'f928494dcb92b86e31a4b5f3fba8daa9d54e614e8e4dcbe9f47f22cfe05a3be1')
    ])
    def test_fetch_go_specific(self, tmpdir, go, name, version, expected_digest):
        """Test fetching of go artifact."""
        digest, path = IndianaJones.fetch_artifact(go,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        path = Path(path)
        assert path.name == '{}.tar.gz'.format(version)
        assert path.exists()
