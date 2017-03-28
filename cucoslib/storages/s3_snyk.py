#!/usr/bin/env python3

import json
from dateutil import parser as datetime_parser
from datetime import datetime, timezone
from . import AmazonS3


class S3Snyk(AmazonS3):
    _S3_SNYK_DB_OBJECT_KEY = 'vulndb.json'
    _S3_METAINFO_OBJECT_KEY = 'meta.json'

    def update_sync_date(self):
        """ Update Snyk sync associated metadata on S3

        :return: datetime when the last sync was done
        """
        if self.object_exists(self._S3_METAINFO_OBJECT_KEY):
            content = self.retrieve_dict(self._S3_METAINFO_OBJECT_KEY)
            last_sync_datetime = datetime_parser.parse(content['updated'])
        else:
            content = {}
            last_sync_datetime = datetime.min.replace(tzinfo=timezone.utc)

        content['updated'] = str(datetime.now(timezone.utc))
        self.store_dict(content, self._S3_METAINFO_OBJECT_KEY)

        return last_sync_datetime

    def store_vulndb(self, cve_db):
        """
        :param cve_db: CVE DB to be stored
        """
        self.store_dict(cve_db, self._S3_SNYK_DB_OBJECT_KEY)

    def retrieve_vulndb(self):
        """ Retrieve vuldb as stored on S3 """
        return self.retrieve_dict(self._S3_SNYK_DB_OBJECT_KEY)
