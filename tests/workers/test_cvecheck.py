"""Tests for the CVEcheckerTask worker task."""

from datadiff.tools import assert_equal
from flexmock import flexmock
from pathlib import Path
import pytest

from f8a_worker.object_cache import EPVCache
from f8a_worker.workers import CVEcheckerTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestCVEchecker(object):
    """Tests for the CVEcheckerTask worker task."""

    @pytest.mark.parametrize(('cve_id', 'score', 'vector', 'severity'), [
        ('CVE-2017-0249', 7.3, 'CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L', 'high'),
        ('cve-2015-1164', 4.3, 'AV:N/AC:M/Au:N/C:N/I:P/A:N', 'medium')
    ])
    def test_get_cve_impact(self, cve_id, score, vector, severity):
        """Test the method CVEcheckerTask.get_cve_impact."""
        score_, vector_, severity_ = CVEcheckerTask.get_cve_impact(cve_id)
        assert score_ == score
        assert vector_ == vector
        assert severity_ == severity

    @pytest.mark.usefixtures('victims_zip_s3')
    def test_npm_servestatic(self):
        """Tests CVE reports for selected package from NPM ecosystem."""
        args = {'ecosystem': 'npm', 'name': 'serve-static', 'version': '1.6.4'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-1164']
        # http://www.cvedetails.com/version/186008/Geddyjs-Geddy-13.0.7.html
        expected_details = [{
            "attribution": "https://github.com/victims/victims-cve-db, CC BY-SA 4.0, modified",
            "cvss": {
                "score": 4.3,
                "vector": "AV:N/AC:M/Au:N/C:N/I:P/A:N"
            },
            "description": "Open redirect vulnerability in the serve-static plugin "
                           "before 1.7.2 for Node.js, when mounted at the root, allows "
                           "remote attackers to redirect users to arbitrary web sites "
                           "and conduct phishing attacks via a // (slash slash) followed "
                           "by a domain in the PATH_INFO to the default URI.\n",
            "id": "CVE-2015-1164",
            "references": [
                "http://nodesecurity.io/advisories/serve-static-open-redirect",
                "https://bugzilla.redhat.com/show_bug.cgi?id=1181917",
                "https://github.com/expressjs/serve-static/issues/26",
                "https://nvd.nist.gov/vuln/detail/CVE-2015-1164",
                "https://github.com/expressjs/serve-static/blob/master/HISTORY.md#165--2015-02-04"
            ],
            "severity": "medium"
        }]
        assert_equal(results.get('details'), expected_details)

    @pytest.mark.usefixtures('victims_zip_s3')
    def test_maven_commons_compress(self):
        """Tests CVE reports for selected packages from Maven ecosystem."""
        args = {'ecosystem': 'maven', 'name': 'org.apache.commons:commons-compress',
                'version': '1.4'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        expected_details = [
            {
                "attribution": "https://github.com/victims/victims-cve-db, CC BY-SA 4.0, modified",
                "cvss": {
                    "score": 5.0,
                    "vector": "AV:N/AC:L/Au:N/C:N/I:N/A:P"
                },
                "description": "Algorithmic complexity vulnerability in the sorting algorithms "
                               "in bzip2 compressing stream (BZip2CompressorOutputStream) "
                               "in Apache Commons Compress before 1.4.1 allows remote attackers "
                               "to cause a denial of service (CPU consumption) via a file "
                               "with many repeating inputs.\n",
                "id": "CVE-2012-2098",
                "references": [
                    "https://nvd.nist.gov/vuln/detail/CVE-2012-2098"
                ],
                "severity": "medium"
            }
        ]
        assert_equal(results.get('details'), expected_details, results.get('details'))

    @pytest.mark.usefixtures('victims_zip_s3')
    def test_python_pyjwt(self):
        """Tests CVE reports for selected package from PyPi ecosystem."""
        args = {'ecosystem': 'pypi', 'name': 'pyjwt', 'version': '1.5.0'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2017-11424']
        # http://www.cvedetails.com/version/94328/Makotemplates-Mako-0.3.3.html
        expected_details = [{
            "attribution": "https://github.com/victims/victims-cve-db, CC BY-SA 4.0, modified",
            "cvss": {
                "score": 5.0,
                "vector": "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:H/A:N"
            },
            "description": "In PyJWT 1.5.0 and below the `invalid_strings` check in "
                           "`HMACAlgorithm.prepare_key` does not account for all PEM "
                           "encoded public keys. Specifically, the PKCS1 PEM encoded "
                           "format would be allowed because it is prefaced with the string "
                           "`-----BEGIN RSA PUBLIC KEY-----` which is not accounted for. "
                           "This enables symmetric/asymmetric key confusion attacks against "
                           "users using the PKCS1 PEM encoded public keys, which would allow "
                           "an attacker to craft JWTs from scratch.\n",
            "id": "CVE-2017-11424",
            "references": [
                "https://github.com/jpadilla/pyjwt/pull/277",
                "https://nvd.nist.gov/vuln/detail/CVE-2017-11424"
            ],
            "severity": "high"
        }]
        assert_equal(results.get('details'), expected_details)

    @pytest.mark.usefixtures('nuget')
    def test_nuget_system_net_http(self):
        """Tests CVE reports for selected package from Nuget ecosystem."""
        args = {'ecosystem': 'nuget', 'name': 'System.Net.Http', 'version': '4.1.1'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        # https://github.com/dotnet/announcements/issues/12
        # http://www.cvedetails.com/version/220163/Microsoft-System.net.http-4.1.1.html
        assert set(results.get('summary')) >= {'CVE-2017-0247', 'CVE-2017-0248',
                                               'CVE-2017-0249', 'CVE-2017-0256'}
        details = results.get('details')
        assert isinstance(details, list) and len(details) >= 4
        for detail in details:
            assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
            assert detail['description']
            assert detail['references']
            assert set(detail['cvss'].keys()) == {'score', 'vector'}
