"""Module for working with VictimsDB data."""

import zipfile
import tempfile
import os
import logging
import requests
from lxml import etree
from yaml import YAMLError, safe_load
from selinon import StoragePool
import shutil
from distutils.version import LooseVersion

from f8a_worker.process import Git


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
        if ecosystem == 'maven':
            return self.java_vulnerabilities
        elif ecosystem == 'pypi':
            return self.python_vulnerabilities
        elif ecosystem == 'npm':
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
        if ecosystem == 'maven':
            return '{g}:{a}'.format(g=affected.get('groupId').strip(),
                                    a=affected.get('artifactId').strip())
        return affected.get('name').strip()

    def _get_package_versions(self, ecosystem, package_name):
        """Get all versions for given package name.

        :param package_name: str, package name
        :return: list of all package versions
        """
        if ecosystem == 'maven':
            return self._get_maven_versions(package_name)
        if ecosystem == 'pypi':
            return self._get_pypi_versions(package_name)
        if ecosystem == 'npm':
            return self._get_npm_versions(package_name)
        return []

    def _get_maven_versions(self, package_name):
        """Get all versions for given Maven package."""
        cached = self._java_versions_cache.get(package_name)
        if cached is not None:
            return cached

        g, a = package_name.split(':')
        g = g.replace('.', '/')

        metadata_filenames = {'maven-metadata.xml', 'maven-metadata-local.xml'}

        versions = set()
        we_good = False
        for filename in metadata_filenames:

            # TODO: maven URL needs to be fetched from RDS
            url = 'http://repo1.maven.org/maven2/{g}/{a}/{f}'.format(g=g, a=a, f=filename)

            try:
                metadata_xml = etree.parse(url)
                we_good = True  # We successfully downloaded at least one of the metadata files
                version_elements = metadata_xml.findall('.//version')
                versions = versions.union({x.text for x in version_elements})
            except OSError:
                # Not both XML files have to exist, so don't freak out yet
                pass

        if not we_good:
            logger.error('Unable to obtain a list of versions for {ga}'.format(ga=ga))

        versions = list(versions)
        self._java_versions_cache[package_name] = versions

        return versions

    def _get_pypi_versions(self, package_name):
        """Get all versions for given Python package."""
        pypi_package_url = 'https://pypi.python.org/pypi/{pkg_name}/json'.format(
            pkg_name=package_name
        )

        response = requests.get(pypi_package_url)
        if response.status_code != 200:
            logger.error('Unable to obtain a list of versions for {pkg_name}'.format(
                pkg_name=package_name
            ))
            return []

        return list({x for x in response.json().get('releases', {})})

    def _get_npm_versions(self, package_name):
        """Get all versions for given NPM package."""
        url = 'https://registry.npmjs.org/{pkg_name}'.format(pkg_name=package_name)

        response = requests.get(url)

        if response.status_code != 200:
            logger.error('Unable to fetch versions for package {pkg_name}'.format(
                pkg_name=package_name
            ))
            return []

        versions = {x for x in response.json().get('versions')}
        return list(versions)

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
    def from_s3(cls):
        """Retrieve the database from S3."""
        db_path = tempfile.mkstemp(prefix='victims-db-')[1]
        try:
            s3 = StoragePool.get_connected_storage('S3VulnDB')
            if not s3.object_exists(cls.ARCHIVE_NAME):
                return None
            s3.retrieve_file(cls.ARCHIVE_NAME, db_path)
            return cls(db_path=db_path)
        except Exception:
            os.remove(db_path)
            raise

    @classmethod
    def from_zip(cls, zip_file):
        """Build the database from given ZIP file."""
        return cls(db_path=zip_file, _cleanup=False)

    @classmethod
    def build_from_git(cls):
        """Build the database from GitHub."""
        db_path = cls._build_from_git()
        return cls(db_path=db_path)

    def __enter__(self):
        """Do nothing special, just enter."""
        return self

    def __exit__(self, *args):
        """Clean up on exit."""
        self.close()
