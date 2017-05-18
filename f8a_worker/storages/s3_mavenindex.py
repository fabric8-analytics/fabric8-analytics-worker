import os
from f8a_worker.process import Archive
from f8a_worker.utils import tempdir
from . import AmazonS3


class S3MavenIndex(AmazonS3):
    _INDEX_DIRNAME = 'central-index'
    _INDEX_ARCHIVE = _INDEX_DIRNAME + '.zip'

    def store_index(self, target_dir):
        """ Zip files in target_dir/central-index dir and store to S3 """
        with tempdir() as temp_dir:
            central_index_dir = os.path.join(target_dir, self._INDEX_DIRNAME)
            archive_path = os.path.join(temp_dir, self._INDEX_ARCHIVE)
            Archive.zip_file(central_index_dir, archive_path, junk_paths=True)
            self.store_file(archive_path, self._INDEX_ARCHIVE)

    def store_index_if_not_exists(self, data_dir):
        if not self.object_exists(self._INDEX_ARCHIVE):
            self.store_depcheck_db(data_dir)

    def retrieve_index_if_exists(self, target_dir):
        """ Retrieve central-index.zip from S3 and extract into target_dir/central-index"""
        if self.object_exists(self._INDEX_ARCHIVE):
            with tempdir() as temp_dir:
                archive_path = os.path.join(temp_dir, self._INDEX_ARCHIVE)
                central_index_dir = os.path.join(target_dir, self._INDEX_DIRNAME)
                self.retrieve_file(self._INDEX_ARCHIVE, archive_path)
                Archive.extract_zip(archive_path, central_index_dir, mkdest=True)
                return True

        return False
