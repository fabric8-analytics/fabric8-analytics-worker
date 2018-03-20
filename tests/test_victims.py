"""Test f8a_worker.victims module."""

from f8a_worker.victims import VictimsDB


def test_java_vulnerabilities(victims_zip):
    """Test VictimsDB.java_vulnerabilities()."""
    with VictimsDB.from_zip(victims_zip) as db:
        vulns = [x for x in db.java_vulnerabilities]
        assert len(vulns) == 3


def test_get_vulnerable_java_packages(victims_zip):
    """Test VictimsDB.get_vulnerable_java_packages()."""
    with VictimsDB.from_zip(victims_zip) as db:
        vulns = [x for x in db.get_vulnerable_java_packages()]
        assert len(vulns) == 3

        expected_packages = [
            'commons-fileupload:commons-fileupload',
            'commons-fileupload:commons-fileupload',
            'org.apache.commons:commons-compress'
        ]
        expected_cves = [
            'CVE-2014-0050',
            'CVE-2016-1000031',
            'CVE-2012-2098'
        ]
        for record in vulns:
            assert record['package'] in expected_packages
            expected_packages.pop(expected_packages.index(record['package']))
            assert record['cve_id'] in expected_cves
            expected_cves.pop(expected_cves.index(record['cve_id']))
