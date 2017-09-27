from flexmock import flexmock
import os
import pytest
from f8a_worker.object_cache import EPVCache
from f8a_worker.workers import CVEcheckerTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestCVEchecker(object):
    @pytest.mark.parametrize(('id_', 'score', 'vector', 'severity'), [
        ('CVE-2017-0249', 7.3, 'CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:L', 'high'),
        ('cve-2015-1164', 4.3, 'AV:N/AC:M/Au:N/C:N/I:P/A:N', 'medium')
    ])
    def test_get_cve_impact(self, id_, score, vector, severity):
        score_, vector_, severity_ = CVEcheckerTask.get_cve_impact(id_)
        assert score_ == score
        assert vector_ == vector
        assert severity_ == severity

    @pytest.mark.usefixtures('npm')
    def test_npm_geddy(self):
        args = {'ecosystem': 'npm', 'name': 'geddy', 'version': '13.0.7'}
        task = CVEcheckerTask.create_test_instance(task_name='security_issues')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results.get('details')
        assert isinstance(details, list) and len(details) == 1
        detail = details[0]
        assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
        assert detail['description']
        assert detail['references']
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
        args = {'ecosystem': 'maven', 'name': 'commons-collections', 'version': '3.2.1'}
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
        extracted = os.path.join(
                        os.path.dirname(
                         os.path.abspath(__file__)), '..', 'data', 'pypi', 'Mako-0.3.3')
        args = {'ecosystem': 'pypi', 'name': 'mako', 'version': '0.3.3'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(extracted)
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

    def test_python_requests(self):
        """ To make sure that python CPE suppression works (issue#131) """
        extracted = os.path.join(
                        os.path.dirname(
                         os.path.abspath(__file__)), '..', 'data', 'pypi', 'requests-2.5.3')
        args = {'ecosystem': 'pypi', 'name': 'requests', 'version': '2.5.3'}
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(extracted)
        task = CVEcheckerTask.create_test_instance(task_name='source_licenses')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results.get('details')
        #  "details": [
        #    {
        #        "cvss": {
        #            "score": 6.8,
        #            "vector": "AV:N/AC:M/Au:?/C:P/I:P/A:P"
        #        },
        #        "description": "The resolve_redirects function in sessions.py ...",
        #        "id": "CVE-2015-2296",
        #        "references": [
        #            "http://advisories.mageia.org/MGASA-2015-0120.html"
        #        ],
        #        "severity": "Medium"
        #    }

        assert isinstance(details, list) and len(details) == 1
        detail = details[0]
        assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
        cvss = detail['cvss']
        assert cvss['score'] == 6.8
        assert cvss['vector'] == 'AV:N/AC:M/Au:?/C:P/I:P/A:P'
        assert detail['id'] == 'CVE-2015-2296'
        assert 'http://advisories.mageia.org/MGASA-2015-0120.html' in detail['references']
        assert detail['severity'] == 'Medium'
        assert results['status'] == 'success'
        assert results['summary'] == ['CVE-2015-2296']

    @pytest.mark.usefixtures('nuget')
    def test_nuget_system_net_http(self):
        args = {'ecosystem': 'nuget', 'name': 'System.Net.Http', 'version': '4.1.1'}
        task = CVEcheckerTask.create_test_instance(task_name='source_licenses')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        # https://github.com/dotnet/announcements/issues/12
        assert set(results.get('summary')) >= {'CVE-2017-0247', 'CVE-2017-0248',
                                               'CVE-2017-0249', 'CVE-2017-0256'}
        details = results.get('details')
        assert isinstance(details, list) and len(details) >= 4
        for detail in details:
            assert set(detail.keys()) == {'cvss', 'description', 'id', 'references', 'severity'}
            assert detail['description']
            assert detail['references']
            assert set(detail['cvss'].keys()) == {'score', 'vector'}
