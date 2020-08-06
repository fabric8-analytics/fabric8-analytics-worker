"""Tests for NewInitPackageFlow module."""

from unittest import TestCase
from selinon import FatalTaskError
from f8a_worker.workers.new_init_package_flow import NewInitPackageFlow

data_v1 = {
        "ecosystem": "dummy_eco",
        "name": "dummy_name",
        "version": "dummy_version"
}

data_v2 = {
        "ecosystem": "golang",
        "name": "dummy_name",
        "version": "dummy_version"
}

data_v3 = {
        "ecosystem": "golang",
        "version": "dummy_version"
}

data_v4 = {
        "name": "dummy_name",
        "version": "dummy_version"
}

data_v5 = {
        "ecosystem": "golang",
        "name": "dummy_name",
}


class TestInitPackageFlowNew(TestCase):
    """Tests for the NewInitPackageFlow task."""

    def _strict_assert(self, assert_cond):
        if not assert_cond:
            raise FatalTaskError("Strict assert failed.")

    def test_execute(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageFlow.execute, self, data_v1)

    def test_execute1(self):
        """Tests for 'execute'."""
        result = NewInitPackageFlow.execute(self, data_v2)
        expected = {'ecosystem': 'golang', 'name': 'dummy_name', 'version': 'dummy_version'}
        assert result == expected

    def test_execute2(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageFlow.execute, self, data_v3)

    def test_execute3(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageFlow.execute, self, data_v4)

    def test_execute4(self):
        """Tests for 'execute'."""
        self.assertRaises(FatalTaskError, NewInitPackageFlow.execute, self, data_v5)
