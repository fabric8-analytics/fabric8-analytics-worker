import glob
import os
import os.path as osp
import pytest
import shutil
import subprocess
import tempfile

from f8a_worker.process import Git, IndianaJones
from f8a_worker.utils import MavenCoordinates


@pytest.fixture
def tmpdir():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp)


class TestGit(object):
    def test_git_add_and_commit_everything_with_dotgit(self, tmpdir):
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
    @pytest.mark.parametrize("name, version, expected_digest", [
        # Prior to npm-2.x.x (Fedora 24)
        # npm client was repackaging modules on download. It modified file permissions inside
        # package.tgz so they matched UID/GID of a user running npm command. Therefore
        # this hash was valid only for user 1000:1000.
        # If the test that checks this fails, it means that the feature is back in npm and we can't
        # rely on the digest of the npm downloaded tarball matching the upstream one.
        # In that case we should probably consider downloading tarballs directly from registry.npmjs.org.
        # because for example AnityaTask relies on this.
        ("abbrev", "1.0.7", "30f6880e415743312a0021a458dd6d26a7211f803a42f1e4a30ebff44d26b7de"),
        ("abbrev", "1.0.4", "8dc0f480571a4a19e74f1abd4f31f6a70f94953d1ccafa16ed1a544a19a6f3a8")
    ])
    def test_fetch_npm_specific(self, tmpdir, npm, name, version, expected_digest):
        cache_path = subprocess.check_output(["npm", "config", "get", "cache"],
                                             universal_newlines=True).strip()
        assert ".npm" in cache_path
        package_digest, path = IndianaJones.fetch_artifact(npm,
                                                           artifact=name,
                                                           version=version,
                                                           target_dir=tmpdir)
        assert len(glob.glob(osp.join(cache_path, name, "*"))) == 1,\
            "there should be just one version of the artifact in the NPM cache"
        assert package_digest == expected_digest
        assert osp.exists(path)
        assert osp.exists(osp.join(osp.join(cache_path, name), version))
        assert osp.exists(osp.join(tmpdir, "package.tgz"))

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('six', '1.0.0', 'ca79c14c8cb5e58912d185f0e07ca9c687e232b7c68c4b73bf1c83ef5979333e'),
    ])
    def test_fetch_pypi_specific(self, tmpdir, pypi, name, version, expected_digest):
        digest, path = IndianaJones.fetch_artifact(pypi,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        assert len(os.listdir(str(tmpdir))) > 1
        glob_whl_path = glob.glob(osp.join(str(tmpdir), "{}-{}*".format(name,
                                                                        version))).pop()
        assert osp.exists(glob_whl_path)

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('permutation', '0.1.7', 'e715cccaccb8e2d1450fbdda85bbe84963a32e9bf612db278cbb3d6781267638')
    ])
    def test_fetch_rubygems_specific(self, tmpdir, rubygems, name, version, expected_digest):
        digest, path = IndianaJones.fetch_artifact(rubygems,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        assert osp.exists(osp.join(str(tmpdir), "{}-{}.gem".format(name,
                                                                   version)))

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('com.rabbitmq:amqp-client', '3.6.1',
         'cb6cdb7de8d37cb1b15b23867435c7dbbeaa1ca4b766f434138a8b9ef131994f'),
        ('org.springframework:spring-aop', '5.0.0.M5',
         '2b51fe492f6a7ed76b27c319b035c289926f399934f9d6bf072baac62ebf4fa5')
    ])
    def test_fetch_maven_specific(self, tmpdir, maven, name, version, expected_digest):
        digest, path = IndianaJones.fetch_artifact(maven,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        _, artifactId = name.split(':', 1)
        assert digest == expected_digest
        assert osp.exists(osp.join(str(tmpdir), '{}-{}.jar'.format(artifactId,
                                                                   version)))

    @pytest.mark.parametrize('name, version, expected_digest', [
        ('NUnit', '3.7.1', 'db714c0a01d8a172e6c378144b1192290263f8c308e8e2baba9c11d9fe165db4'),
    ])
    def test_fetch_nuget_specific(self, tmpdir, nuget, name, version, expected_digest):
        digest, path = IndianaJones.fetch_artifact(nuget,
                                                   artifact=name,
                                                   version=version,
                                                   target_dir=str(tmpdir))
        assert digest == expected_digest
        assert osp.exists(osp.join(str(tmpdir), '{}.{}.nupkg'.format(name.lower(),
                                                                     version)))

    @pytest.mark.parametrize('name, version, expected_repos', [
        ('org.apache.ant:ant', '1.9.4',
         ['http://central.maven.org/maven2/',
          'https://repository.apache.org/content/repositories/releases/',
          'https://maven.repository.redhat.com/ga/']),
        ('org.netbeans.api:org-netbeans-modules-java-source', 'RELEASE81',
         ['http://bits.netbeans.org/maven2/']),
        ('org.springframework.boot:spring-boot-starter-thymeleaf', '1.3.0.M2',
         ['http://repo.spring.io/milestone/',
          'https://artifacts.alfresco.com/nexus/content/repositories/public/'])
    ])
    def test_webscrape_maven_repos_urls(self, name, version, expected_repos):
        artifact_coords = MavenCoordinates.from_str(name)
        artifact_coords.version = version
        repos = list(IndianaJones.webscrape_maven_repos_urls(artifact_coords))
        assert repos == expected_repos
