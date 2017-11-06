from dateutil import parser as datetime_parser
from datetime import datetime, timezone
import os
from f8a_worker.errors import TaskError
from f8a_worker.process import Archive
from f8a_worker.utils import cwd, tempdir
from . import AmazonS3


class S3VulnDB(AmazonS3):
    DEPCHECK_DB_FILENAME = 'dc.h2.db'
    DEPCHECK_DB_ARCHIVE = DEPCHECK_DB_FILENAME + '.zip'
    VICTIMS_DB_DIR = 'victims-cve-db'
    VICTIMS_DB_ARCHIVE = VICTIMS_DB_DIR + '.zip'

    METAINFO_OBJECT_KEY = 'meta.json'

    def update_sync_date(self):
        """ Update sync associated metadata

        :return: timestamp of the previous sync
        """
        datetime_now = datetime.now(timezone.utc)
        if self.object_exists(self.METAINFO_OBJECT_KEY):
            content = self.retrieve_dict(self.METAINFO_OBJECT_KEY)
            previous_sync_datetime = datetime_parser.parse(content['updated'])
        else:
            content = {}
            previous_sync_datetime = datetime_now

        content['updated'] = str(datetime_now)
        self.store_dict(content, self.METAINFO_OBJECT_KEY)

        return previous_sync_datetime.replace(tzinfo=timezone.utc).timestamp()

    def store_depcheck_db(self, data_dir):
        """ Zip CVE DB file and store to S3 """
        with tempdir() as archive_dir:
            archive_path = os.path.join(archive_dir, self.DEPCHECK_DB_ARCHIVE)
            db_file_path = os.path.join(data_dir, self.DEPCHECK_DB_FILENAME)
            try:
                Archive.zip_file(db_file_path, archive_path, junk_paths=True)
            except TaskError:
                pass
            else:
                self.store_file(archive_path, self.DEPCHECK_DB_ARCHIVE)

    def retrieve_depcheck_db_if_exists(self, data_dir):
        """ Retrieve zipped CVE DB file as stored on S3 and extract"""
        if self.object_exists(self.DEPCHECK_DB_ARCHIVE):
            with tempdir() as archive_dir:
                archive_path = os.path.join(archive_dir, self.DEPCHECK_DB_ARCHIVE)
                self.retrieve_file(self.DEPCHECK_DB_ARCHIVE, archive_path)
                Archive.extract_zip(archive_path, data_dir)
                return True
        return False

    def store_victims_db(self, data_dir):
        """ Zip Victims CVE DB and store to S3 """
        with tempdir() as archive_dir:
            archive_path = os.path.join(archive_dir, self.VICTIMS_DB_ARCHIVE)
            with cwd(data_dir):
                try:
                    Archive.zip_file(self.VICTIMS_DB_DIR, archive_path)
                except TaskError:
                    pass
                else:
                    self.store_file(archive_path, self.VICTIMS_DB_ARCHIVE)

    def retrieve_victims_db_if_exists(self, data_dir):
        """ Retrieve zipped Victims CVE DB file as stored on S3 and extract"""
        if self.object_exists(self.VICTIMS_DB_ARCHIVE):
            with tempdir() as archive_dir:
                archive_path = os.path.join(archive_dir, self.VICTIMS_DB_ARCHIVE)
                self.retrieve_file(self.VICTIMS_DB_ARCHIVE, archive_path)
                Archive.extract_zip(archive_path, data_dir)
                return True
        return False
