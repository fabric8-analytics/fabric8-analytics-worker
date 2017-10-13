import os
import botocore
from f8a_worker.errors import TaskError
from f8a_worker.process import Archive
from f8a_worker.utils import tempdir
from . import AmazonS3


class S3MavenIndex(AmazonS3):
    _INDEX_DIRNAME = 'central-index'
    _INDEX_ARCHIVE = _INDEX_DIRNAME + '.zip'

    _LAST_OFFSET_OBJECT_KEY = 'last_offset.json'
    _DEFAULT_LAST_OFFSET = 0

    def store_index(self, target_dir):
        """ Zip files in target_dir/central-index dir and store to S3 """
        with tempdir() as temp_dir:
            central_index_dir = os.path.join(target_dir, self._INDEX_DIRNAME)
            archive_path = os.path.join(temp_dir, self._INDEX_ARCHIVE)
            try:
                Archive.zip_file(central_index_dir, archive_path, junk_paths=True)
            except TaskError:
                pass
            else:
                self.store_file(archive_path, self._INDEX_ARCHIVE)

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

    def get_last_offset(self):
        """Get used offset pointing to maven index checker.

        Last offset is used in jobs service to schedule new releases of maven packages.
        We need to store offset that was used for the last time in order to keep track
        where we left off.
        """
        try:
            content = self.retrieve_dict(self._LAST_OFFSET_OBJECT_KEY)
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'NoSuchKey':
                return self._DEFAULT_LAST_OFFSET
            else:
                # Some another error, not no such file
                raise

        return content.get('last_offset', self._DEFAULT_LAST_OFFSET)

    def set_last_offset(self, offset):
        """Set used offset pointing to maven index checker."""
        content = {
            'last_offset': offset
        }
        self.store_dict(content, self._LAST_OFFSET_OBJECT_KEY)
