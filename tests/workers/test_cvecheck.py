import pytest

from cucoslib.workers import CVEcheckerTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestCVEchecker(object):
    def test_npm_scan(self):
        # TODO: Needs Snyk vulndb in S3
        assert True

    def test_maven_scan(self):
        # TODO: We'd need to download some jar to run the scan
        assert True
