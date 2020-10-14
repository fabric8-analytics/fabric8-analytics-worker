"""Tests for NewGraphImporterTask module."""

from unittest import TestCase, mock
from f8a_worker.workers.new_graph_importer import NewGraphImporterTask

data = {
        "ecosystem": "dummy_eco",
        "name": "dummy_name",
        "version": "dummy_version"
}


class Response:
    """Custom response class."""

    status_code = 200
    text = 'dummy_data'


class ErrorResponse:
    """Custom response class for error."""

    status_code = 404
    text = 'dummy_data'


class TestGraphImporterNew(TestCase):
    """Tests for the NewGraphImporterTask task."""

    def _strict_assert(self, assert_cond):
        if not assert_cond:
            False

    @mock.patch('f8a_worker.workers.new_graph_importer.requests.post', return_value=ErrorResponse())
    def test_execute(self, _mock1):
        """Tests for 'execute'."""
        self.assertRaises(RuntimeError, NewGraphImporterTask.execute, self, data)

    @mock.patch('f8a_worker.workers.new_graph_importer.requests.post', return_value=Response())
    def test_execute1(self, _mock1):
        """Tests for 'execute'."""
        NewGraphImporterTask.execute(self, data)
