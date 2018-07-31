"""Test f8a_worker.workers.victims module."""

import requests

from f8a_worker.workers import VictimsCheck
from f8a_worker.victims import VictimsDB


def test_get_vulnerable_packages(maven, victims_zip):
    """Test VictimsCheck.get_vulnerable_packages()."""
    with VictimsDB.from_zip(victims_zip) as db:
        task = VictimsCheck.create_test_instance()
        packages = task.get_vulnerable_packages(db, maven)
        assert len(packages) == 2

        expected_packages = [
            'commons-fileupload:commons-fileupload',
            'org.apache.commons:commons-compress'
        ]
        for package, data in packages.items():
            assert package in expected_packages
            if package == 'commons-fileupload:commons-fileupload':
                # there are multiple vulnerabilities for this package
                assert len(data) == 2
            else:
                assert len(data) == 1


def test_mark_in_graph(maven, victims_zip, mocker):
    """Test VictimsCheck.mark_in_graph()."""
    graph_mock = mocker.patch("f8a_worker.workers.victims.update_properties")
    graph_mock.return_value = None

    # Total number of affected artifacts (EPVs) for all 3 CVEs in our test database;
    vuln_count = 11

    with VictimsDB.from_zip(victims_zip) as db:
        task = VictimsCheck.create_test_instance()
        packages = task.get_vulnerable_packages(db, maven)
        task.mark_in_graph(packages, maven)

    assert graph_mock.call_count == vuln_count


def test_notify_gemini(maven, victims_zip, mocker):
    """Test VictimsCheck.notify_gemini()."""
    response = requests.Response()
    response.status_code = 200
    sa_mock = mocker.patch("f8a_worker.workers.victims.VictimsCheck.init_auth_sa_token")
    sa_mock.return_value = 'access_token'
    gemini_mock = mocker.patch("requests.post")
    gemini_mock.return_value = response

    # Total number of affected packages
    vuln_count = 2

    with VictimsDB.from_zip(victims_zip) as db:
        task = VictimsCheck.create_test_instance()
        packages = task.get_vulnerable_packages(db, maven)
        task.notify_gemini(packages, maven)

    assert gemini_mock.call_count == vuln_count
