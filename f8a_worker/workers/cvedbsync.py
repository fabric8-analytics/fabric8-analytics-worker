"""Update vulnerability sources."""

from selinon import StoragePool
from f8a_worker.base import BaseTask
from f8a_worker.solver import get_ecosystem_solver, OSSIndexDependencyParser
from f8a_worker.workers import CVEcheckerTask


class CVEDBSyncTask(BaseTask):
    """Update vulnerability sources."""

    def components_to_scan(self, previous_sync_timestamp, only_already_scanned):
        """Get EPV that were recently updated in OSS Index, so they can contain new vulnerabilities.

        Get components (e:p:v) that were recently (since previous_sync_timestamp) updated
        in OSS Index, which means that they can contain new vulnerabilities.

        :param previous_sync_timestamp: timestamp of previous check
        :param only_already_scanned: include already scanned components only
        :return: generator of e:p:v
        """
        # TODO: reduce cyclomatic complexity
        to_scan = []
        for ecosystem in ['nuget']:
            ecosystem_solver = get_ecosystem_solver(self.storage.get_ecosystem(ecosystem),
                                                    with_parser=OSSIndexDependencyParser())
            self.log.debug("Retrieving new %s vulnerabilities from OSS Index", ecosystem)
            ossindex_updated_packages = CVEcheckerTask.\
                query_ossindex_vulnerability_fromtill(ecosystem=ecosystem,
                                                      from_time=previous_sync_timestamp)
            for ossindex_updated_package in ossindex_updated_packages:
                if ecosystem == 'maven':
                    package_name = "{g}:{n}".format(g=ossindex_updated_package['group'],
                                                    n=ossindex_updated_package['name'])
                else:
                    package_name = ossindex_updated_package['name']
                package_affected_versions = set()
                for vulnerability in ossindex_updated_package.get('vulnerabilities', []):
                    for version_string in vulnerability.get('versions', []):
                        try:
                            resolved_versions = ecosystem_solver.\
                                solve(["{} {}".format(package_name, version_string)],
                                      all_versions=True)
                        except Exception:
                            self.log.exception("Failed to resolve %r for %s:%s", version_string,
                                               ecosystem, package_name)
                            continue
                        resolved_versions = resolved_versions.get(package_name, [])
                        if only_already_scanned:
                            already_scanned_versions =\
                                [ver for ver in resolved_versions if
                                 self.storage.get_analysis_count(ecosystem, package_name, ver) > 0]
                            package_affected_versions.update(already_scanned_versions)
                        else:
                            package_affected_versions.update(resolved_versions)

                for version in package_affected_versions:
                    to_scan.append({
                        'ecosystem': ecosystem,
                        'name': package_name,
                        'version': version
                    })
        msg = "Components to be {prefix}scanned for vulnerabilities: {components}".\
            format(prefix="re-" if only_already_scanned else "",
                   components=to_scan)
        self.log.info(msg)
        return to_scan

    def execute(self, arguments):
        """Start the task.

        :param arguments: optional argument 'only_already_scanned' to run only
        on already analysed packages
        :return: EPV dict describing which packages should be analysed
        """
        only_already_scanned = arguments.pop('only_already_scanned', True) if arguments else True
        ignore_modification_time = (arguments.pop('ignore_modification_time', False)
                                    if arguments else False)

        CVEcheckerTask.update_depcheck_db_on_s3()

        self.log.debug('Updating sync associated metadata')
        s3 = StoragePool.get_connected_storage('S3VulnDB')
        previous_sync_timestamp = s3.update_sync_date()
        if ignore_modification_time:
            previous_sync_timestamp = 0
        # get components which might have new vulnerabilities since previous sync
        to_scan = self.components_to_scan(previous_sync_timestamp, only_already_scanned)
        return {'modified': to_scan}
