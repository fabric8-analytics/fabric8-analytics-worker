import glob
import os
import os.path as osp
import pytest
import requests
import shutil
import subprocess
from xmlrpc.client import ServerProxy
import time
import tempfile
from lxml import etree

from cucoslib.enums import EcosystemBackend
from cucoslib.models import Ecosystem
from cucoslib.process import Git, IndianaJones

NPM_MODULE_NAME = "dezalgo"
NPM_MODULE_VERSION = "1.0.2"
# Prior to npm-2.x.x (Fedora 24)
# npm client was repackaging modules on download. It modified file permissions inside
# package.tgz so they matched UID/GID of a user running npm command. Therefore
# this hash was valid only for user 1000:1000.
# If the test that checks this fails, it means that the feature is back in npm and we can't
# rely on the digest of the npm downloaded tarball matching the upstream one.
# In that case we should probably consider downloading tarballs directly from registry.npmjs.org.
# because for example AnityaTask relies on this.
NPM_MODULE_DIGEST = '8db082250efa45673f344bb809c7cfa1ce37ca9274de29635a40d1e7df6d6114'
PYPI_MODULE_NAME = "six"
PYPI_MODULE_VERSION = "1.0.0"
PYPI_MODULE_DIGEST = 'ca79c14c8cb5e58912d185f0e07ca9c687e232b7c68c4b73bf1c83ef5979333e'
RUBYGEMS_MODULE_NAME = "permutation"
RUBYGEMS_MODULE_VERSION = "0.1.7"
RUBYGEMS_MODULE_DIGEST = 'e715cccaccb8e2d1450fbdda85bbe84963a32e9bf612db278cbb3d6781267638'
MAVEN_MODULE_NAME = "com.rabbitmq:amqp-client"
MAVEN_MODULE_VERSION = "3.6.1"
MAVEN_MODULE_DIGEST = 'cb6cdb7de8d37cb1b15b23867435c7dbbeaa1ca4b766f434138a8b9ef131994f'


npm = Ecosystem(name='npm', backend=EcosystemBackend.npm)
pypi = Ecosystem(name='pypi', backend=EcosystemBackend.pypi)
rubygems = Ecosystem(name='rubygems', backend=EcosystemBackend.rubygems)
maven = Ecosystem(name='maven', backend=EcosystemBackend.maven)


@pytest.fixture
def tmpdir():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp)


def test_git_add_and_commit_everything_with_dotgit(tmpdir):
    # if there's a .git file somewhere in the archive, we don't want it to fail adding
    subprocess.check_output(['git', 'init', str(tmpdir)], universal_newlines=True)
    d = os.path.join(str(tmpdir), 'foo')
    os.makedirs(d)
    with open(os.path.join(d, '.git'), 'w') as f:
        f.write('gitdir: /this/doesnt/exist/hehehe')
    # we need at least one normal file for git to commit
    with open(os.path.join(d, 'foo'), 'w') as f:
        pass
    g = Git.create_git(str(tmpdir))
    g.add_and_commit_everything()


@pytest.mark.flaky(reruns=5)
def test_fetch_npm_latest(tmpdir):
    cache_path = subprocess.check_output(["npm", "config", "get", "cache"], universal_newlines=True).strip()
    assert ".npm" in cache_path
    module_cache_path = osp.join(cache_path, NPM_MODULE_NAME)

    # this could go really really bad if npm returns "/"
    shutil.rmtree(module_cache_path, ignore_errors=True)  # we don't care if it doesn't exist

    npm_url = "https://registry.npmjs.org/{}".format(NPM_MODULE_NAME)
    response = requests.get(npm_url, json=True)
    try:
        assert response.status_code == 200, response.text
    except AssertionError:
        # Let's try again, but give the remote service some time to catch a breath
        time.sleep(1)
        raise
    module_json = response.json()
    latest_version = sorted(module_json["versions"].keys()).pop()
    IndianaJones.fetch_artifact(npm,
                                artifact=NPM_MODULE_NAME, target_dir=str(tmpdir))
    assert len(glob.glob(osp.join(cache_path, NPM_MODULE_NAME, "*"))) == 1,\
        "there should be just one version of the artifact in the NPM cache"

    assert osp.exists(osp.join(module_cache_path, latest_version))
    assert osp.exists(osp.join(str(tmpdir), "package.tgz"))


@pytest.mark.parametrize("package,version,digest", [
    ("abbrev", "1.0.7", "30f6880e415743312a0021a458dd6d26a7211f803a42f1e4a30ebff44d26b7de"),
    ("abbrev", "1.0.4", "8dc0f480571a4a19e74f1abd4f31f6a70f94953d1ccafa16ed1a544a19a6f3a8")
])
def test_fetch_npm_specific(tmpdir, package, version, digest):
    cache_path = subprocess.check_output(["npm", "config", "get", "cache"], universal_newlines=True).strip()
    assert ".npm" in cache_path

    package_digest, path = IndianaJones.fetch_artifact(
        npm, artifact=package,
        version=version, target_dir=tmpdir)

    assert len(glob.glob(osp.join(cache_path, package, "*"))) == 1,\
        "there should be just one version of the artifact in the NPM cache"

    assert package_digest == digest
    assert osp.exists(path)
    assert osp.exists(osp.join(osp.join(cache_path, package), version))
    assert osp.exists(osp.join(tmpdir, "package.tgz"))


def test_fetch_pypi_latest(tmpdir):
    # stolen from internets
    # http://code.activestate.com/recipes/577708-check-for-package-updates-on-pypi-works-best-in-pi/

    pypi_rpc = ServerProxy('https://pypi.python.org/pypi')
    latest_version = pypi_rpc.package_releases(PYPI_MODULE_NAME)[0]

    IndianaJones.fetch_artifact(pypi,
                                artifact=PYPI_MODULE_NAME, target_dir=str(tmpdir))

    assert len(os.listdir(str(tmpdir))) > 1
    glob_whl_path = glob.glob(osp.join(str(tmpdir),
                                       "{}-{}*".format(PYPI_MODULE_NAME, latest_version))).pop()
    assert osp.exists(glob_whl_path)


def test_fetch_pypi_specific(tmpdir):
    digest, path = IndianaJones.fetch_artifact(
        pypi, artifact=PYPI_MODULE_NAME,
        version=PYPI_MODULE_VERSION, target_dir=str(tmpdir))

    assert digest == PYPI_MODULE_DIGEST
    assert len(os.listdir(str(tmpdir))) > 1
    glob_whl_path = glob.glob(osp.join(str(tmpdir), "{}-{}*".format(PYPI_MODULE_NAME,
                                                                    PYPI_MODULE_VERSION))).pop()
    assert osp.exists(glob_whl_path)


@pytest.mark.flaky(reruns=5)
def test_fetch_rubygems_latest(tmpdir):
    rubygems_url = "https://rubygems.org/api/v1/versions/{}/latest.json".format(RUBYGEMS_MODULE_NAME)
    response = requests.get(rubygems_url, json=True)
    try:
        assert response.status_code == 200, response.text
    except AssertionError:
        # Let's try again, but give the remote service some time to catch a breath
        time.sleep(1)
        raise
    latest_version = response.json()["version"]
    IndianaJones.fetch_artifact(rubygems,
                                artifact=RUBYGEMS_MODULE_NAME, target_dir=str(tmpdir))

    assert osp.exists(osp.join(str(tmpdir), "{}-{}.gem".format(RUBYGEMS_MODULE_NAME,
                                                               latest_version)))


def test_fetch_rubygems_specific(tmpdir):
    digest, path = IndianaJones.fetch_artifact(
        rubygems,
        artifact=RUBYGEMS_MODULE_NAME,
        version=RUBYGEMS_MODULE_VERSION, target_dir=str(tmpdir))

    assert digest == RUBYGEMS_MODULE_DIGEST
    assert osp.exists(osp.join(str(tmpdir), "{}-{}.gem".format(RUBYGEMS_MODULE_NAME,
                                                               RUBYGEMS_MODULE_VERSION)))


def test_fetch_maven_specific(tmpdir):
    digest, path = IndianaJones.fetch_artifact(maven,
                                               artifact=MAVEN_MODULE_NAME,
                                               version=MAVEN_MODULE_VERSION, target_dir=str(tmpdir))

    _, artifactId = MAVEN_MODULE_NAME.split(':', 1)

    assert digest == MAVEN_MODULE_DIGEST
    assert osp.exists(osp.join(str(tmpdir), '{}-{}.jar'.format(artifactId, MAVEN_MODULE_VERSION)))


def test_fetch_maven_latest(tmpdir):
    maven_central_url = 'http://repo1.maven.org/maven2'

    groupId, artifactId = MAVEN_MODULE_NAME.split(':', 1)
    groupId = groupId.replace('.', '/')

    # get maven-metadata.xml from the repository
    url_template = '{base}/{group}/{artifact}/maven-metadata.xml'.format(base=maven_central_url,
                                                                         group=groupId,
                                                                         artifact=artifactId)
    meta = etree.parse(url_template)

    # get latest version
    version = meta.xpath('/metadata/versioning/latest')[0].text

    IndianaJones.fetch_artifact(maven,
                                artifact=MAVEN_MODULE_NAME,
                                version=None, target_dir=str(tmpdir))

    assert osp.exists(osp.join(str(tmpdir), '{}-{}.jar'.format(artifactId, version)))
