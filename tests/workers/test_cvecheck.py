from flexmock import flexmock
import os
import pytest
from cucoslib.object_cache import EPVCache
from cucoslib.workers import CVEcheckerTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestCVEchecker(object):
    def test_npm_geddy(self, npm):
        args = {'ecosystem': 'npm', 'name': 'geddy', 'version': '13.0.7'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results.get('details')
        # [
        #    {
        #        "cvss": {
        #           "score": 5.0,
        #            "vector": "AV:N/AC:L/Au:N/C:P/I:N/A:N"
        #        },
        #        "description": "## Overview\n\nGeddy ...",
        #        "id": "CVE-2015-5688",
        #        "references": [],
        #        "severity": "medium"
        #    }
        # ]
        assert isinstance(details, list) and len(details) == 1
        detail = details[0]
        assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
        cvss = detail['cvss']
        assert cvss['score'] == 5.0
        assert cvss['vector'] == 'AV:N/AC:L/Au:N/C:P/I:N/A:N'
        assert detail['id'] == 'CVE-2015-5688'
        assert detail['severity'] == 'medium'
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-5688']

    def test_maven_commons_collections(self):
        jar_path = os.path.join(
                    os.path.dirname(
                     os.path.abspath(__file__)), '..', 'data', 'maven',
                                                 'commons-collections-3.2.1.jar')
        args = {'ecosystem': 'maven', 'name': 'mako', 'version': '0.3.3'}
        flexmock(EPVCache).should_receive('get_source_tarball').and_return(jar_path)
        task = CVEcheckerTask.create_test_instance(task_name='source_licenses')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results.get('details')
        #   "details": [
        #        {
        #            "cvss": {
        #                "score": 7.5,
        #                "vector": "AV:N/AC:L/Au:?/C:P/I:P/A:P"
        #            },
        #        "description": "...",
        #        "id": "CVE-2015-6420",
        #        "references": [
        #            "http://www.securityfocus.com/bid/78872",
        #            "http://tools.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-20151209-java-deserialization",
        #            "https://h20566.www2.hpe.com/portal/site/hpsc/public/kb/docDisplay?docId=emr_na-c05376917",
        #            "https://h20566.www2.hpe.com/portal/site/hpsc/public/kb/docDisplay?docId=emr_na-c05390722"
        #            ],
        #        "severity": "High"
        #        }
        #    ],
        assert isinstance(details, list) and len(details) == 1
        detail = details[0]
        assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
        cvss = detail['cvss']
        assert cvss['score'] == 7.5
        assert cvss['vector'] == 'AV:N/AC:L/Au:?/C:P/I:P/A:P'
        assert detail['id'] == 'CVE-2015-6420'
        assert 'http://www.securityfocus.com/bid/78872' in detail['references']
        assert detail['severity'] == 'High'
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-6420']

    def test_python_mako(self):
        egg_info_dir = os.path.join(
                        os.path.dirname(
                         os.path.abspath(__file__)), '..', 'data', 'Mako.egg-info')
        args = {'ecosystem': 'pypi', 'name': 'mako', 'version': '0.3.3'}
        flexmock(EPVCache).should_receive('get_source_tarball').and_return('mako.tgz')
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(egg_info_dir)
        task = CVEcheckerTask.create_test_instance(task_name='source_licenses')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results.get('details')
        #   "details": [
        #        {
        #            "cvss": {
        #                "score": 4.3,
        #                "vector": "AV:N/AC:M/Au:?/C:?/I:P/A:?"
        #            },
        #            "description": "Mako before 0.3.4 ...",
        #            "id": "CVE-2010-2480",
        #            "references": [
        #                "http://www.makotemplates.org/CHANGES",
        #                "http://bugs.python.org/issue9061",
        #                "http://lists.opensuse.org/opensuse-security-announce/2010-08/msg00001.html"
        #            ],
        #            "severity": "Medium"
        #        }
        #    ]
        assert isinstance(details, list) and len(details) == 1
        detail = details[0]
        assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
        cvss = detail['cvss']
        assert cvss['score'] == 4.3
        assert cvss['vector'] == 'AV:N/AC:M/Au:?/C:?/I:P/A:?'
        assert detail['id'] == 'CVE-2010-2480'
        assert 'http://bugs.python.org/issue9061' in detail['references']
        assert detail['severity'] == 'Medium'
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2010-2480']
