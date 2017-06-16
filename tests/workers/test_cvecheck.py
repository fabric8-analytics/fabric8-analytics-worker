import pytest

from cucoslib.enums import EcosystemBackend
from cucoslib.models import Ecosystem
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

    def test_maven_scan(self):
        # TODO: We'd need to download some jar to run the scan
        assert True

    def test_python_scan(self):
        assert True
