from dateutil import parser as datetime_parser
from datetime import datetime, timezone
import os
from tempfile import TemporaryDirectory

from f8a_worker.errors import TaskError
from f8a_worker.process import Archive
from f8a_worker.utils import cwd
from . import AmazonS3


class S3VulnDB(AmazonS3):
    DEPCHECK_DB_FILENAME = 'dc.h2.db'
    DEPCHECK_DB_ARCHIVE = DEPCHECK_DB_FILENAME + '.zip'
    VICTIMS_DB_ARCHIVE = 'victims-cve-db.zip'

    METAINFO_OBJECT_KEY = 'meta.json'

    def update_sync_date(self):
        """Update sync associated metadata.

        :return: timestamp of the previous sync
        """
        datetime_now = datetime.utcnow()
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
        """Zip CVE DB file and store to S3."""
        with TemporaryDirectory() as archive_dir:
            archive_path = os.path.join(archive_dir, self.DEPCHECK_DB_ARCHIVE)
            db_file_path = os.path.join(data_dir, self.DEPCHECK_DB_FILENAME)
            try:
                Archive.zip_file(db_file_path, archive_path, junk_paths=True)
            except TaskError:
                pass
            else:
                self.store_file(archive_path, self.DEPCHECK_DB_ARCHIVE)

    def retrieve_depcheck_db_if_exists(self, data_dir):
        """Retrieve zipped CVE DB file as stored on S3 and extract."""
        if self.object_exists(self.DEPCHECK_DB_ARCHIVE):
            with TemporaryDirectory() as archive_dir:
                archive_path = os.path.join(archive_dir, self.DEPCHECK_DB_ARCHIVE)
                self.retrieve_file(self.DEPCHECK_DB_ARCHIVE, archive_path)
                Archive.extract_zip(archive_path, data_dir)
                return True
        return False

    def store_victims_db(self, victims_db_dir):
        """Zip victims_db_dir/* and store to S3 as VICTIMS_DB_ARCHIVE."""
        with TemporaryDirectory() as temp_archive_dir:
            temp_archive_path = os.path.join(temp_archive_dir, self.VICTIMS_DB_ARCHIVE)
            with cwd(victims_db_dir):
                Archive.zip_file('.', temp_archive_path)
                self.store_file(temp_archive_path, self.VICTIMS_DB_ARCHIVE)

    def retrieve_victims_db_if_exists(self, victims_db_dir):
        """Retrieve VICTIMS_DB_ARCHIVE from S3 and extract into victims_db_dir."""
        if self.object_exists(self.VICTIMS_DB_ARCHIVE):
            with TemporaryDirectory() as temp_archive_dir:
                temp_archive_path = os.path.join(temp_archive_dir, self.VICTIMS_DB_ARCHIVE)
                self.retrieve_file(self.VICTIMS_DB_ARCHIVE, temp_archive_path)
                Archive.extract_zip(temp_archive_path, victims_db_dir)
                return True
        return False
