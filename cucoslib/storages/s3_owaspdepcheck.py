import os
from . import AmazonS3


class S3OWASPDepCheck(AmazonS3):
    _S3_DEPCHECK_DB_OBJECT_KEY = 'dc.h2.db'
    _DB_FILE_PATH = os.path.join(os.getenv('OWASP_DEP_CHECK_PATH',
                                           default=os.path.join('opt', 'dependency-check')),
                                 'data',
                                 _S3_DEPCHECK_DB_OBJECT_KEY)

    def store_depcheck_db(self):
        """ Store CVE DB file to S3 """
        self.store_file(self._DB_FILE_PATH, self._S3_DEPCHECK_DB_OBJECT_KEY)

    def retrieve_depcheck_db_if_exists(self):
        """ Retrieve CVE DB file as stored on S3 """
        if self.object_exists(self._S3_DEPCHECK_DB_OBJECT_KEY):
            self.retrieve_file(self._S3_DEPCHECK_DB_OBJECT_KEY, self._DB_FILE_PATH)
