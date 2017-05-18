import os
from f8a_worker.process import Archive
from f8a_worker.utils import tempdir
from . import AmazonS3


class S3OWASPDepCheck(AmazonS3):
    _DB_FILENAME = 'dc.h2.db'
    _DB_ARCHIVE = _DB_FILENAME + '.zip'

    def store_depcheck_db(self, data_dir):
        """ Zip CVE DB file and store to S3 """
        with tempdir() as archive_dir:
            archive_path = os.path.join(archive_dir, self._DB_ARCHIVE)
            db_file_path = os.path.join(data_dir, self._DB_FILENAME)
            Archive.zip_file(db_file_path, archive_path, junk_paths=True)
            self.store_file(archive_path, self._DB_ARCHIVE)

    def store_depcheck_db_if_not_exists(self, data_dir):
        if not self.object_exists(self._DB_ARCHIVE):
            self.store_depcheck_db(data_dir)

    def retrieve_depcheck_db_if_exists(self, data_dir):
        """ Retrieve zipped CVE DB file as stored on S3 and extract"""
        if self.object_exists(self._DB_ARCHIVE):
            with tempdir() as archive_dir:
                archive_path = os.path.join(archive_dir, self._DB_ARCHIVE)
                self.retrieve_file(self._DB_ARCHIVE, archive_path)
                Archive.extract_zip(archive_path, data_dir)
                return True

        return False
