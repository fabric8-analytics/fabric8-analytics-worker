import os
from tempfile import gettempdir
from cucoslib.process import Archive
from . import AmazonS3


class S3OWASPDepCheck(AmazonS3):
    _DB_FILENAME = 'dc.h2.db'
    _DB_ARCHIVE = _DB_FILENAME + '.zip'
    _DB_DATA_PATH = os.path.join(os.getenv('OWASP_DEP_CHECK_PATH',
                                           default=os.path.join('opt', 'dependency-check')),
                                 'data')
    _DB_FILE_PATH = os.path.join(_DB_DATA_PATH, _DB_FILENAME)
    _DB_ARCHIVE_PATH = os.path.join(gettempdir(), _DB_ARCHIVE)

    def store_depcheck_db(self):
        """ Zip CVE DB file and store to S3 """
        # 272Mib -> 44MiB(deflated 84%)
        Archive.zip_file(self._DB_FILE_PATH, self._DB_ARCHIVE_PATH, junk_paths=True)
        self.store_file(self._DB_ARCHIVE_PATH, self._DB_ARCHIVE)

    def store_depcheck_db_if_not_exists(self):
        if not self.object_exists(self._DB_ARCHIVE):
            self.store_depcheck_db()

    def retrieve_depcheck_db_if_exists(self):
        """ Retrieve zipped CVE DB file as stored on S3 and extract"""
        if self.object_exists(self._DB_ARCHIVE):
            self.retrieve_file(self._DB_ARCHIVE, self._DB_ARCHIVE_PATH)
            Archive.extract_zip(self._DB_ARCHIVE_PATH, self._DB_DATA_PATH)
