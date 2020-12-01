"""Tests for NewInitPackageFlow module."""

from unittest import TestCase
from selinon import FatalTaskError
from f8a_worker.workers.new_init_package_analysis_flow import NewInitPackageAnlysisFlow

data_v1 = {
        "ecosystem": "dummy_eco",
        "name": "dummy_name"
}

data_v2 = {
        "ecosystem": "golang",
        "name": "dummy_name"
}


class TestInitPackageFlowNew(TestCase):
    """Tests for the NewInitPackageFlow task."""

    def _strict_assert(self, assert_cond):
        if not assert_cond:
            False

    def test_execute(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageAnlysisFlow.execute, self, data_v1)

    def test_execute1(self):
        """Tests for 'execute'."""
        result = NewInitPackageAnlysisFlow.execute(self, data_v2)
        expected = {'ecosystem': 'golang', 'name': 'dummy_name'}
        assert result == expected
