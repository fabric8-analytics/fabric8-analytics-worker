import os
import json
from dateutil import parser as datetime_parser
from selinon import StoragePool
from cucoslib.process import Git
from cucoslib.utils import cwd, TimedCommand, tempdir
from cucoslib.base import BaseTask
from cucoslib.solver import get_ecosystem_solver


class CVEDBSyncTask(BaseTask):
    """ Download and update NPM vulnerability database """
    _VULNDB_GIT_REPO = 'https://github.com/snyk/vulndb'
    _VULNDB_FILENAME = 'vulndb.json'

    def _update_dep_check_db(self, data_dir):
        depcheck = os.path.join(os.environ['OWASP_DEP_CHECK_PATH'], 'bin', 'dependency-check.sh')
        self.log.debug('Updating OWASP Dependency-Check CVE DB')
        TimedCommand.get_command_output([depcheck, '--updateonly', '--data', data_dir],
                                        timeout=1800)

    def _get_snyk_vulndb(self):
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
                TimedCommand.get_command_output(['npm', 'install'])
                # generate database (json in file)
                self.log.debug("Generating snyk/vulndb")
                TimedCommand.get_command_output([os.path.join('cli', 'shrink.js'),
                                                'data',
                                                self._VULNDB_FILENAME])
                # parse the JSON so we are sure that we have a valid JSON
                with open(self._VULNDB_FILENAME) as f:
                    return json.load(f)

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
                if self.storage.get_analysis_count('npm', package_name, version) > 0:
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

        s3 = StoragePool.get_connected_storage('S3OWASPDepCheck')
        with tempdir() as temp_data_dir:
            s3.retrieve_depcheck_db_if_exists(temp_data_dir)
            self._update_dep_check_db(temp_data_dir)
            s3.store_depcheck_db(temp_data_dir)

        cve_db = self._get_snyk_vulndb()
        s3 = StoragePool.get_connected_storage('S3Snyk')
        s3.store_vulndb(cve_db)
        last_sync_datetime = s3.update_sync_date()

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
