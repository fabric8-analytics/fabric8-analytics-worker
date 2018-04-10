"""Test f8a_worker.workers.victims module."""

from f8a_worker.workers import VictimsCheck
from f8a_worker.victims import VictimsDB


def test_get_vulnerable_packages(victims_zip):
    """Test VictimsCheck.get_vulnerable_packages()."""
    with VictimsDB.from_zip(victims_zip) as db:
        task = VictimsCheck.create_test_instance()
        packages = task.get_vulnerable_packages(db)
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


def test_mark_in_graph(victims_zip, mocker):
    """Test VictimsCheck.mark_in_graph()."""
    graph_mock = mocker.patch("f8a_worker.workers.victims.update_properties")
    graph_mock.return_value = None

    # Total number of affected artifacts (EPVs) for all 3 CVEs in our test database;
    vuln_count = 11

    with VictimsDB.from_zip(victims_zip) as db:
        task = VictimsCheck.create_test_instance()
        packages = task.get_vulnerable_packages(db)
        task.mark_in_graph(packages)

    assert graph_mock.call_count == vuln_count
