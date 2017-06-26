import json
import os

import pytest
import flexmock
import requests

from f8a_worker.workers import csmock_worker


dummy_package_dir = os.path.abspath(os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "dummy-package",
))
dummy_package_path = os.path.join(
    dummy_package_dir,
    "dummy.tar.gz"
)
dummy_results_path = os.path.join(
    dummy_package_dir,
    "csmock-output.json"
)


def mock_csmock(args):
    with open(dummy_results_path) as fp:
        return json.load(fp)


def test_csmock_tool(tmpdir):
    t = str(tmpdir)
    os.chdir(t)
    sa = csmock_worker.StaticAnalysis(dummy_package_path)
    results = sa.analyze()

    assert [d["checker"] for d in results["defects"]]
    assert isinstance(results["defects"], list)
    assert isinstance(results["defects"][0]["events"], list)


@pytest.mark.offline
def test_offline_csmock_tool():
    flexmock.flexmock(csmock_worker, csmock=mock_csmock)
    task = csmock_worker.StaticAnalysis(dummy_package_path)
    results = task.analyze()

    assert [d["checker"] for d in results["defects"]]
    assert isinstance(results["defects"], list)
    assert isinstance(results["defects"][0]["events"], list)


def test_csmock_worker(tmpdir):
    six_tb_url = "https://pypi.python.org/packages/b3/b2/238e2590826bfdd113244a40d9d3eb26918bd798fc187e2360a8367068db/six-1.10.0.tar.gz"
    tb_path = os.path.join(str(tmpdir), "six-1.10.0.tar.gz")
    r = requests.get(six_tb_url, stream=True)
    if r.status_code == 200:
        with open(tb_path, 'wb') as f:
            for chunk in r.iter_content(4096):
                f.write(chunk)

    t = csmock_worker.CsmockTask.create_test_instance(task_name='static_analysis')
    args = {'source_tarball_path': tb_path, 'cache_path': str(tmpdir)}
    results = t.execute(args)

    assert results["status"] == "success"
    # naive schema check
    assert results["summary"]
    assert results["summary"]["PROSPECTOR_WARNING"]["count"] > 0  # this is tied to python
    assert results["details"]["scan"]
    assert isinstance(results["details"]["defects"], list)
    assert results["details"]["defects"][0]["checker"]
    assert isinstance(results["details"]["defects"][0]["events"], list)
    # ensure results are independent
    scan_keys = set(results["details"]["scan"].keys())
    assert not {"time-created", "time-finished", "host", "store-results-to"}.intersection(scan_keys)


@pytest.mark.offline
def test_offline_csmock_worker(tmpdir):
    flexmock.flexmock(csmock_worker, csmock=mock_csmock)
    t = csmock_worker.CsmockTask.create_test_instance(task_name='static_analysis')
    args = {'source_tarball_path': dummy_package_path, 'cache_path': str(tmpdir)}
    results = t.execute(args)

    assert results["status"] == "success"
    # naive schema check
    assert results["summary"]
    assert results["summary"]["PROSPECTOR_WARNING"]["count"] > 0  # this is tied to python
    assert results["details"]["scan"]
    assert isinstance(results["details"]["defects"], list)
    assert results["details"]["defects"][0]["checker"]
    assert isinstance(results["details"]["defects"][0]["events"], list)
