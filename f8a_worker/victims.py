"""Module for working with VictimsDB data."""

import zipfile
import tempfile
import os
import logging
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

    def __init__(self, db_path, _cleanup=True):
        """Construct VictimsDB."""
        self._java_vulnerabilities = []
        self._python_vulnerabilities = []
        self._db_path = db_path
        self._java_versions_cache = {}
        self._cleanup = _cleanup  # perform clean up?

    def close(self):
        """Perform cleanup."""
        if self._cleanup:
            os.remove(self._db_path)

    @property
    def java_vulnerabilities(self):
        """Yield Java vulnerabilities, one at a time."""
        if not self._java_vulnerabilities:
            self._read_db()
        for vulnerability in self._java_vulnerabilities:
            yield vulnerability

    def _read_db(self):
        with zipfile.ZipFile(self._db_path) as zipf:
            for zip_info in zipf.filelist:
                if not zip_info.filename.endswith(('.yaml', '.yml')):
                    continue
                stream = zipf.read(zip_info)
                try:
                    vulnerability = safe_load(stream)
                    # Only Java/Maven is supported at the moment
                    if zip_info.filename.startswith('database/java/'):
                        self._java_vulnerabilities.append(vulnerability)
                except YAMLError:
                    logger.exception('Failed to load YAML file: {f}'.format(f=zip_info.filename))

    def get_vulnerable_java_packages(self):
        """Yield simplified details about Java vulnerable packages."""
        for vulnerability in self.java_vulnerabilities:
            for affected in vulnerability.get('affected', []):
                ga = '{g}:{a}'.format(g=affected.get('groupId'),
                                      a=affected.get('artifactId'))

                all_versions = self.get_package_versions(ga)
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
                    'package': ga,
                    'cve_id': 'CVE-' + vulnerability.get('cve'),
                    'cvss_v2': vulnerability.get('cvss_v2'),
                    'cvss_v3': vulnerability.get('cvss_v3'),
                    'affected': affected_versions,
                    'not_affected': not_affected_versions
                }

    def get_package_versions(self, ga):
        """Get all versions for given groupId:artifactId.

        Only Maven is supported at the moment.

        :param ga: str, package name in form of groupId:artifactId
        :return: list of all package versions
        """
        cached = self._java_versions_cache.get(ga)
        if cached is not None:
            return cached

        g, a = ga.split(':')
        g = g.replace('.', '/')

        metadata_filenames = {'maven-metadata.xml', 'maven-metadata-local.xml'}

        versions = set()
        we_good = False
        for filename in metadata_filenames:

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
        self._java_versions_cache[ga] = versions

        return versions

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
        db_path = tempfile.mkstemp(prefix='victims-db-')
        try:
            s3 = StoragePool.get_connected_storage('S3VulnDB')
            if s3.object_exists(cls.ARCHIVE_NAME):
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
