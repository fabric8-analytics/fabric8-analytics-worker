import os
import json
from dateutil import parser as datetime_parser
from datetime import datetime, timezone
from selinon import StoragePool
from cucoslib.base import BaseTask
from cucoslib.process import Git
from cucoslib.schemas import SchemaRef
from cucoslib.solver import get_ecosystem_solver
from cucoslib.utils import analysis_count, cwd, get_command_output, tempdir


class SnykSyncTask(BaseTask):
    """ Download and update NPM vulnerability database """

    _VULNDB_GIT_REPO = 'https://github.com/snyk/vulndb'
    _VULNDB_FILENAME = 'vulndb.json'
    _DEFAULT_S3_BUCKET_NAME = '{DEPLOYMENT_PREFIX}-bayesian-core-snyk'
    _S3_BUCKET_NAME = os.getenv('{DEPLOYMENT_PREFIX}-SNYK_S3_BUCKET_NAME', _DEFAULT_S3_BUCKET_NAME)
    _S3_METAINFO_OBJECT_KEY = 'meta.json'

    @property
    def s3_bucket_name(self):
        """
        :return: bucket name expanded based on env variables
        """
        return self._S3_BUCKET_NAME.format(**os.environ)

    def _get_cve_db(self):
        """
        :return: retrieve Snyk CVE db
        """

        with tempdir() as vulndb_dir:
            # clone vulndb git repo
            self.log.debug("Cloning snyk/vulndb repo")
            Git.clone(self._VULNDB_GIT_REPO, vulndb_dir)
            with cwd(vulndb_dir):
                # install dependencies
                self.log.debug("Installing snyk/vulndb dependencies")
                get_command_output(['npm', 'install'])
                # generate database (json in file)
                self.log.debug("Generating snyk/vulndb")
                get_command_output([os.path.join('cli', 'shrink.js'),
                                    'data',
                                    self._VULNDB_FILENAME])
                # parse the JSON so we are sure that we have a valid JSON
                with open(self._VULNDB_FILENAME) as f:
                    return json.load(f)

    def _store_cve_db(self, cve_db, s3):
        """
        :param cve_db: CVE DB to be stored
        :param s3: S3 instance where to store the DB
        """
        s3.store_blob(
            blob=s3.dict2blob(cve_db),
            object_key=self._VULNDB_FILENAME,
            bucket_name=self.s3_bucket_name,
            versioned=True,
            encrypted=False
        )

    def _update_sync_date(self, s3):
        """ Update Snyk sync associated metadata on S3

        :param s3: S3 instance where to store metadata
        :return: datetime when the last sync was done
        """
        if s3.object_exists(bucket_name=self.s3_bucket_name, object_key=self._S3_METAINFO_OBJECT_KEY):
            content = s3.retrieve_blob(bucket_name=self.s3_bucket_name, object_key=self._S3_METAINFO_OBJECT_KEY)
            content = json.loads(content.decode())
            last_sync_datetime = datetime_parser.parse(content['updated'])
        else:
            content = {}
            last_sync_datetime = datetime.min.replace(tzinfo=timezone.utc)

        content['updated'] = str(datetime.now(timezone.utc))
        s3.store_blob(
            blob=s3.dict2blob(content),
            object_key=self._S3_METAINFO_OBJECT_KEY,
            bucket_name=self.s3_bucket_name,
            versioned=False,
            encrypted=False,
        )

        return last_sync_datetime

    def _get_versions_to_scan(self, package_name, version_string, only_already_scanned):
        """ Compute versions that should be scanned based on version string

        :param package_name: name of the package which versions should be resolved
        :param version_string: version string for the package
        :param only_already_scanned: if True analyse only packages that were already analysed
        :return: list of versions that should be analysed
        """
        solver = get_ecosystem_solver(self.storage.get_ecosystem('npm'))
        try:
            resolved = solver.solve(["{} {}".format(package_name, version_string)], all_versions=True)
        except:
            self.log.exception("Failed to resolve versions for package '%s'", package_name)
            return []

        resolved_versions = resolved.get(package_name, [])

        if only_already_scanned:
            result = []
            for version in resolved_versions:
                if analysis_count('npm', package_name, version) > 0:
                    result.append(version)
            return result
        else:
            return resolved_versions

    def execute(self, arguments):
        """

        :param arguments: optional argument 'only_already_scanned' to run only on already analysed packages
        :return: EPV dict describing which packages should be analysed
        """
        only_already_scanned = arguments.pop('only_already_scanned', True) if arguments else True
        ignore_modification_time = arguments.pop('ignore_modification_time', False) if arguments else False
        self._strict_assert(not arguments)

        s3 = StoragePool.get_connected_storage('AmazonS3')

        cve_db = self._get_cve_db()
        self._store_cve_db(cve_db, s3)
        last_sync_datetime = self._update_sync_date(s3)

        to_update = []
        for package_name, cve_records in cve_db.get('npm', {}).items():
            for record in cve_records:
                modification_time = datetime_parser.parse(record['modificationTime'])

                if ignore_modification_time or modification_time >= last_sync_datetime:
                    affected_versions = self._get_versions_to_scan(
                        package_name,
                        record['semver']['vulnerable'],
                        only_already_scanned
                    )

                    for version in affected_versions:
                        to_update.append({
                            'ecosystem': 'npm',
                            'name': package_name,
                            'version': version
                        })

        return {'modified': to_update}
