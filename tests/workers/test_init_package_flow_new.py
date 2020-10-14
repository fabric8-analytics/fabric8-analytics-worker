"""Tests for NewInitPackageFlow module."""

from unittest import TestCase
from selinon import FatalTaskError
from f8a_worker.workers.new_init_package_flow import NewInitPackageFlow

data_v1 = {
        "ecosystem": "dummy_eco",
        "url": "dummy_name"
}

data_v2 = {
        "ecosystem": "golang",
        "url": "dummy_name"
}

data_v3 = {
        "ecosystem": "golang",
        "url": "https://github.com/jaegertracing/jaeger"
}


class TestInitPackageFlowNew(TestCase):
    """Tests for the NewInitPackageFlow task."""

    def _strict_assert(self, assert_cond):
        if not assert_cond:
            False

    def test_execute(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageFlow.execute, self, data_v1)

    def test_execute1(self):
        """Tests for 'execute'."""
        result = NewInitPackageFlow.execute(self, data_v2)
        expected = {'ecosystem': 'golang', 'url': ''}
        assert result == expected

    def test_execute2(self):
        """Tests for 'execute'."""
        result = NewInitPackageFlow.execute(self, data_v3)
        expected = {'ecosystem': 'golang', 'url': 'https://github.com/jaegertracing/jaeger'}
        assert result == expected
