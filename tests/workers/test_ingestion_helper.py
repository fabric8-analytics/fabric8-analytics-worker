"""Tests for classes from ingestion_helper module."""

from f8a_worker.workers.ingestion_helper import ingest_epv
from unittest import mock

data_v1 = {
        "npm": [{
                "package": "pkg1",
                "version": "ver1"
            },
            {
                "package": "pkg2",
                "version": "ver2"
            }],
        "maven": [{
                "package": "pkg1",
                "version": "ver1"
            },
            {
                "package": "pkg2",
                "version": "ver2"
            }],
        "pypi": [{
                "package": "pkg1",
                "version": "ver1"
            },
            {
                "package": "pkg2",
                "version": "ver2"
            }]}


class Response:
    status_code = 201

    def json(self):
        return {}


@mock.patch('f8a_worker.workers.ingestion_helper.requests.post', return_value=Response())
def test_ingest_epv(_mock):
    """Test ingestion-epv."""

    res = ingest_epv(data_v1)
    expected = {
        'maven': {'result': {}, 'status_code': 201},
        'npm': {'result': {}, 'status_code': 201},
        'pypi': {'result': {}, 'status_code': 201}}
    assert res == expected
