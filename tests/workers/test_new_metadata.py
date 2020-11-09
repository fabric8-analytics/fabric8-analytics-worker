"""Tests for the function f8a_worker.workers.new_metadata."""
from unittest import TestCase, mock
from f8a_worker.workers.new_metadata import NewMetaDataTask


data_v1 = {
        "ecosystem": "dummy_eco",
        "name": "dummy_name",
        "version": "dummy_version"
}

data_v2 = {
        "ecosystem": "dummy_eco",
        "name": "",
        "version": "dummy_version"
}


class GolangUtils():
    """Test  class."""

    def __init__(self, pkg):
        """Test Function."""
        self.pkg = pkg

    def get_license(self):
        """Test Function."""
        if self.pkg:
            return ['MIT']
        else:
            return None


class S3():
    """Dummy Class."""

    def store_data(self, arguments, result):
        """Test Function."""
        pass


class TestNewMetaDataTask(TestCase):
    """Tests for the NewInitPackageFlow task."""

    def store_data_to_s3(self, arguments, s3, result):
        """Test Function."""
        if not arguments:
            raise
        if not s3:
            raise
        if not result:
            raise
        pass

    @mock.patch('f8a_worker.workers.new_metadata.StoragePool.get_connected_storage',
                return_value='')
    @mock.patch('f8a_worker.workers.new_metadata.GolangUtils',
                return_value=GolangUtils(data_v1['name']))
    def test_execute(self, _mock1, _mock2):
        """Tests for 'execute'."""
        result = NewMetaDataTask.execute(self, data_v1)
        expected = {'ecosystem': 'dummy_eco', 'name': 'dummy_name', 'version': 'dummy_version'}
        assert result == expected

    @mock.patch('f8a_worker.workers.new_metadata.StoragePool.get_connected_storage',
                return_value='')
    @mock.patch('f8a_worker.workers.new_metadata.GolangUtils',
                return_value=GolangUtils(data_v2['name']))
    def test_execute1(self, _mock1, _mock2):
        """Tests for 'execute'."""
        result = NewMetaDataTask.execute(self, data_v2)
        expected = {'ecosystem': 'dummy_eco', 'name': '', 'version': 'dummy_version'}
        assert result == expected
