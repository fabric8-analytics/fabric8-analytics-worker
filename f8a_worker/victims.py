"""Module for working with VictimsDB data."""

import zipfile
import tempfile
import os
import logging
from yaml import YAMLError, safe_load
from selinon import StoragePool
import shutil
from distutils.version import LooseVersion

from f8a_worker.process import Git
from f8a_worker.solver import MavenReleasesFetcher, PypiReleasesFetcher, NpmReleasesFetcher


VICTIMS_URL = 'https://github.com/victims/victims-cve-db.git'
F8A_CVEDB_URL = 'https://github.com/fabric8-analytics/cvedb.git'


logger = logging.getLogger(__name__)


# Inspired by https://github.com/victims/victims-cve-db/blob/master/victims-cve-db-cli.py
class VictimsDB(object):
    """Wrapper around Victims CVE database."""

    ARCHIVE_NAME = 'victims-cve-db.zip'

    ECOSYSTEM_MAP = {
        'maven': 'java',
        'pypi': 'python',
        'npm': 'javascript'
    }

    def __init__(self, db_path, _cleanup=True):
        """Construct VictimsDB."""
        self._java_vulnerabilities = []
        self._python_vulnerabilities = []
        self._javascript_vulnerabilities = []
        self._db_path = db_path

        self._java_versions_cache = {}
        self._python_versions_cache = {}
        self._javascript_versions_cache = {}

        self._cleanup = _cleanup  # perform clean up?

        self._read_db()

    def close(self):
        """Perform cleanup."""
        if self._cleanup:
            os.remove(self._db_path)

    @property
    def java_vulnerabilities(self):
        """Yield Java vulnerabilities, one at a time."""
        for vulnerability in self._java_vulnerabilities:
            yield vulnerability

    @property
    def python_vulnerabilities(self):
        """Yield Python vulnerabilities, one at a time."""
        for vulnerability in self._python_vulnerabilities:
            yield vulnerability

    @property
    def javascript_vulnerabilities(self):
        """Yield JavaScript vulnerabilities, one at a time."""
        for vulnerability in self._javascript_vulnerabilities:
            yield vulnerability

    def get_vulnerabilities_for_epv(self, ecosystem, package, version):
        """Get list of vulnerabilities for given EPV."""
        all_vulnerabilities = self.get_vulnerabilities_for_ecosystem(ecosystem)
        package = package.strip().lower()

        vulnerabilities = []
        for vulnerability in all_vulnerabilities:
            for affected in vulnerability.get('affected', []):
                norm_affected = self._get_package_name(ecosystem, affected).lower()
                if norm_affected == package and \
                   self.is_version_affected(affected.get('version', []), version):
                    vulnerabilities.append(vulnerability)
        return vulnerabilities

    def _read_db(self):
        with zipfile.ZipFile(self._db_path) as zipf:
            for zip_info in zipf.filelist:
                if not zip_info.filename.endswith(('.yaml', '.yml')):
                    continue
                self._register_cve(zipf, zip_info)

    def _register_cve(self, zipf, zip_info):
        stream = zipf.read(zip_info)
        try:
            vulnerability = safe_load(stream)
            if zip_info.filename.startswith('database/java/'):
                self._java_vulnerabilities.append(vulnerability)
            if zip_info.filename.startswith('database/python/'):
                self._python_vulnerabilities.append(vulnerability)
            if zip_info.filename.startswith('database/javascript/'):
                self._javascript_vulnerabilities.append(vulnerability)
        except YAMLError:
            logger.exception('Failed to load YAML file: {f}'.format(f=zip_info.filename))

    def get_vulnerabilities_for_ecosystem(self, ecosystem):
        """Get all vulnerabilities for given ecosystem."""
        if ecosystem.name == 'maven':
            return self.java_vulnerabilities
        elif ecosystem.name == 'pypi':
            return self.python_vulnerabilities
        elif ecosystem.name == 'npm':
            return self.javascript_vulnerabilities
        else:
            raise ValueError('Unsupported ecosystem: {e}'.format(e=ecosystem))

    def get_details_for_ecosystem(self, ecosystem):
        """Yield simplified details about vulnerable packages from given ecosystem."""
        vulnerabilities = self.get_vulnerabilities_for_ecosystem(ecosystem)

        for vulnerability in vulnerabilities:
            for affected in vulnerability.get('affected', []):
                package_name = self._get_package_name(ecosystem, affected)

                all_versions = self._get_package_versions(ecosystem, package_name)
                try:
                    affected_versions = [x for x in all_versions
                                         if self.is_version_affected(affected.get('version'), x)]
                except TypeError:
                    logger.warning('Failed to process versions in {cid}'.format(
                        cid=vulnerability.get('cve'))
                    )
                    continue
                not_affected_versions = list(set(all_versions) - set(affected_versions))

                yield {
                    'package': package_name,
                    'cve_id': 'CVE-' + vulnerability.get('cve'),
                    'cvss_v2': vulnerability.get('cvss_v2'),
                    'cvss_v3': vulnerability.get('cvss_v3'),
                    'affected': affected_versions,
                    'not_affected': not_affected_versions
                }

    def _get_package_name(self, ecosystem, affected):
        if ecosystem.name == 'maven':
            return '{g}:{a}'.format(g=affected.get('groupId').strip(),
                                    a=affected.get('artifactId').strip())
        return affected.get('name').strip()

    def _get_package_versions(self, ecosystem, package_name):
        """Get all versions for given package name.

        :param ecosystem: f8a_worker.models.Ecosystem, ecosystem
        :param package_name: str, package name
        :return: list of all package versions
        """
        # Intentionally not checking ecosystem backend here.
        # We simply don't know about CVEs in 3rd party repositories.
        if ecosystem.name == 'maven':
            return MavenReleasesFetcher(ecosystem).fetch_releases(package_name)[1]
        if ecosystem.name == 'pypi':
            return PypiReleasesFetcher(ecosystem).fetch_releases(package_name)[1]
        if ecosystem.name == 'npm':
            return NpmReleasesFetcher(ecosystem).fetch_releases(package_name)[1]
        return []

    @staticmethod
    def is_version_affected(affected_versions, checked_version):
        """Return True if `checked_version` is among `affected_versions`."""
        checked_version = LooseVersion(checked_version)
        for version_range in affected_versions:
            operator = version_range[:2]
            if operator not in ('==', '<='):
                continue
            # https://github.com/victims/victims-cve-db#version-string-common
            if ',' in version_range:
                version = LooseVersion(version_range[2:].split(',')[0])
                series = LooseVersion(version_range.split(',')[1])
            else:
                version = LooseVersion(version_range[2:])
                series = None

            if operator == '==':
                if checked_version == version:
                    return True
            elif operator == '<=':
                if series:
                    if series <= checked_version <= version:
                        return True
                else:
                    if checked_version <= version:
                        return True
        return False

    @classmethod
    def _build_from_git(cls):
        """Build the database from upstream GitHub and our own.

        We do this before we contribute back to Victims.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone VictimsDB and create a ZIP out of it
            with tempfile.TemporaryDirectory() as tf:
                git = Git.clone(VICTIMS_URL, path=tf, single_branch=True)
                victims_zip_path = git.archive(basename='victims', basedir=temp_dir, format='zip')

            # Clone f8a CveDB and create a ZIP out of it
            with tempfile.TemporaryDirectory() as tf:
                git = Git.clone(F8A_CVEDB_URL, path=tf, single_branch=True)
                cvedb_zip_path = git.archive(basename='cvedb', basedir=temp_dir, format='zip')

            # Merge the two ZIP files
            with zipfile.ZipFile(victims_zip_path, 'a') as victims_zip:
                cvedb_zip = zipfile.ZipFile(cvedb_zip_path, 'r')
                for n in cvedb_zip.namelist():

                    victims_zip.writestr(n, cvedb_zip.open(n).read())

            db_path = tempfile.mkstemp(prefix='victims-db-', suffix='.zip')[1]
            try:
                # Copy the uber-ZIP to the target location
                shutil.copyfile(victims_zip_path, db_path)
                return db_path
            except Exception:
                os.remove(db_path)
                raise

    def store_on_s3(self):
        """Store the database on S3."""
        s3 = StoragePool.get_connected_storage('S3VulnDB')
        s3.store_file(self._db_path, self.ARCHIVE_NAME)

    @classmethod
    def from_s3(cls, **kwargs):
        """Retrieve the database from S3."""
        db_path = tempfile.mkstemp(prefix='victims-db-')[1]
        try:
            s3 = StoragePool.get_connected_storage('S3VulnDB')
            if not s3.object_exists(cls.ARCHIVE_NAME):
                return None
            s3.retrieve_file(cls.ARCHIVE_NAME, db_path)
            return cls(db_path=db_path, **kwargs)
        except Exception:
            os.remove(db_path)
            raise

    @classmethod
    def from_zip(cls, zip_file, **kwargs):
        """Build the database from given ZIP file."""
        return cls(db_path=zip_file, _cleanup=False, **kwargs)

    @classmethod
    def build_from_git(cls, **kwargs):
        """Build the database from GitHub."""
        db_path = cls._build_from_git()
        return cls(db_path=db_path, **kwargs)

    def __enter__(self):
        """Do nothing special, just enter."""
        return self

    def __exit__(self, *args):
        """Clean up on exit."""
        self.close()


class FilteredVictimsDB(VictimsDB):
    """Filtered Victims CVE database.

    Subset of the Victims CVE database containing only "wanted" CVEs.
    """

    def __init__(self, db_path, _cleanup=True, wanted=None):
        """Construct FilteredVictimsDB."""
        self._wanted_cves = wanted or set()
        super().__init__(db_path, _cleanup=_cleanup)

    def _register_cve(self, zipf, zip_info):
        stream = zipf.read(zip_info)
        try:
            vulnerability = safe_load(stream)

            # filter out unwanted CVEs
            if vulnerability.get('cve') not in self._wanted_cves:
                return

            if zip_info.filename.startswith('database/java/'):
                self._java_vulnerabilities.append(vulnerability)
            if zip_info.filename.startswith('database/python/'):
                self._python_vulnerabilities.append(vulnerability)
            if zip_info.filename.startswith('database/javascript/'):
                self._javascript_vulnerabilities.append(vulnerability)
        except YAMLError:
            logger.exception('Failed to load YAML file: {f}'.format(f=zip_info.filename))
