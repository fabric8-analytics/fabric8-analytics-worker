#!/usr/bin/env python3

"""Classes that implements EPV cache and artifact cache."""

import os
import shutil
import logging
from selinon import StoragePool
from f8a_worker.defaults import configuration
from f8a_worker.process import Archive
from f8a_worker.models import EcosystemBackend, Ecosystem


class EPVCache(object):
    """Encapsulation of basic operations on EPV artifacts.

    Object that encapsulates basic operations on EPV artifacts and their
    items, all operations are done lazily
    """

    log = logging.getLogger(__name__)
    _POM_XML_NAME = 'pom.xml'
    _SOURCE_JAR_NAME = 'package-source.jar'
    _EXTRACTED_SOURCE_TARBALL_DIR = 'extracted_package'
    _EXTRACTED_SOURCE_JAR_DIR = 'extracted_jar'
    # Meta-information about artifact
    _META_JSON_NAME = 'meta.json'

    def __init__(self, ecosystem, name, version, cache_dir, is_temporary=False):
        """Initialize all attributes of the EPVCache during object instantiation.

        :param ecosystem: ecosystem for the given EPV
        :param name: name for the given EPV
        :param version: version of the given EPV
        :param cache_dir: path to dir on the filesystem that should be used for caching artifacts
        :param is_temporary: if True, then objects of certain age will be automatically deleted from
                             the underlying storage
        """
        self.ecosystem = ecosystem
        self.name = name
        self.version = version
        self.cache_dir = cache_dir
        self._eco_obj = None
        storage_name = 'S3Artifacts' if not is_temporary else 'S3TempArtifacts'
        self._s3 = StoragePool.get_connected_storage(storage_name)
        self._postgres = StoragePool.get_connected_storage('BayesianPostgres')
        self._base_object_key = "{ecosystem}/{name}/{version}".format(ecosystem=ecosystem,
                                                                      name=name,
                                                                      version=version)
        self._extracted_tarball_dir = os.path.join(self.cache_dir,
                                                   self._EXTRACTED_SOURCE_TARBALL_DIR)
        self._extracted_source_jar_dir = os.path.join(self.cache_dir,
                                                      self._EXTRACTED_SOURCE_JAR_DIR)
        self._pom_xml_path = os.path.join(self.cache_dir, self._POM_XML_NAME)
        self._source_jar_path = os.path.join(self.cache_dir, self._SOURCE_JAR_NAME)
        self._pom_xml_object_key = "{}/{}".format(self._base_object_key, self._POM_XML_NAME)
        self._source_jar_object_key = "{}/{}".format(self._base_object_key, self._SOURCE_JAR_NAME)

        # Based on actual tarball name which can vary based on ecosystem - see meta.json
        self._source_tarball_path = None
        self._source_tarball_object_key = None

        # Meta-information about artifact
        self._meta = None
        self._meta_json_object_key = "{}/{}".format(self._base_object_key, self._META_JSON_NAME)

    def _retrieve_s3_object(self, object_key, dst_path):
        """Retrieve object stored in S3."""
        self.log.debug("Retrieving object '%s' from bucket '%s' to '%s'", object_key,
                       self._s3.bucket_name, dst_path)
        basedir = os.path.dirname(dst_path)
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        self._s3.retrieve_file(object_key, dst_path)

    def _get_meta(self):
        """Get artifact meta-information stored on S3.

        :return: None if there is no meta.json
        """
        if not self._meta:
            try:
                self._meta = self._s3.retrieve_dict(self._meta_json_object_key)
            except Exception:
                self.log.warning("Failed to retrieve %s", self._meta_json_object_key)
                return None
        return self._meta

    def _has_meta(self):
        """Test if there is associated meta.json for the given EPV.

        :return: True if there is associated meta.json for the given EPV
        """
        # as this call is done privately and meta.json is stored inside
        # ObjectCache we can assume that we will need meta info later, so
        # download them directly
        return self._get_meta() is not None

    def _put_meta(self, tarball_name):
        """Store meta-information about artifact.

        :param tarball_name: tarball name to be stored
        """
        tarball_json = {
            'tarball_name': tarball_name
        }
        self._meta = tarball_json
        self._s3.store_dict(tarball_json, self._meta_json_object_key)

    def _construct_source_tarball_names(self):
        """Construct source tarball object key and source tarball path based on meta-information."""
        if self._source_tarball_object_key and self._source_tarball_path:
            return

        meta = self._get_meta()
        if meta is None:
            raise ValueError("Cannot construct tarball names, is tarball on S3?")
        self._source_tarball_path = os.path.join(self.cache_dir, meta['tarball_name'])
        self._source_tarball_object_key = "{}/{}".format(self._base_object_key,
                                                         meta['tarball_name'])

    def _get_object_cached(self, object_key, local_path):
        """Retrieve object from S3 if not cached, otherwise use locally cached one.

        :param object_key: object key to be used when getting remote object
        :param local_path: path where the object should be placed locally
        :return: path to cached local object
        """
        if not os.path.isfile(local_path):
            self._retrieve_s3_object(object_key, local_path)
        return local_path

    def remove_files(self):
        """Remove all files that are cached for the given EPVCache."""
        self.log.debug("Removing cached files for %s/%s/%s", self.ecosystem, self.name,
                       self.version)
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def get_source_tarball(self):
        """Retrieve source tarball for the given EPV.

        :return: path to the given tarball
        """
        self._construct_source_tarball_names()
        return self._get_object_cached(self._source_tarball_object_key, self._source_tarball_path)

    def has_source_tarball(self):
        """Test if there is available source tarball in the S3 bucket.

        :return: True if there is available source tarball in the S3 bucket
        """
        if not self._has_meta():
            return False

        self._construct_source_tarball_names()
        return self._s3.object_exists(self._source_tarball_object_key)

    def put_source_tarball(self, source_tarball_path):
        """Upload source tarball to S3.

        :param source_tarball_path: path to source tarball
        """
        self._put_meta(os.path.basename(source_tarball_path))
        self._construct_source_tarball_names()
        self._s3.store_file(source_tarball_path, self._source_tarball_object_key)

    def get_extracted_source_tarball(self):
        """Get path to the extracted package tarball.

        :return: path to the extracted package tarball
        """
        self._construct_source_tarball_names()
        if not os.path.isdir(self._extracted_tarball_dir):
            source_tarball_path = self.get_source_tarball()
            os.makedirs(self._extracted_tarball_dir)
            try:
                Archive.extract(source_tarball_path, self._extracted_tarball_dir)
            except Exception:
                # remove in case of failure so if one catches the exception,
                # the extraction code is correctly called again
                shutil.rmtree(self._extracted_tarball_dir, ignore_errors=True)
                raise

        return self._extracted_tarball_dir

    def get_pom_xml(self):
        """Get path to the pom.xml file.

        :return: path to the pom.xml file
        """
        return self._get_object_cached(self._pom_xml_object_key, self._pom_xml_path)

    def put_pom_xml(self, pom_xml_path):
        """Upload pom.xml to the remote S3 bucket.

        :param pom_xml_path: path to pom.xml file
        """
        self._s3.store_file(pom_xml_path, self._pom_xml_object_key)

    def has_pom_xml(self):
        """Test if the given EPV has pom.xml in the remote S3 bucket.

        :return: True if the given EPV has pom.xml in the remote S3 bucket
        """
        return self._s3.object_exists(self._pom_xml_object_key)

    def get_source_jar(self):
        """Get package source jar file (un-extracted).

        :return: path to raw source jar file
        """
        return self._get_object_cached(self._source_jar_object_key, self._source_jar_path)

    def get_extracted_source_jar(self):
        """Get extracted package source jar file.

        :return: path to extracted source jar file
        """
        if not os.path.isdir(self._extracted_source_jar_dir):
            source_jar_path = self.get_source_jar()
            try:
                Archive.extract(source_jar_path, self._extracted_source_jar_dir)
            except Exception:
                # remove in case of failure so if one catches the exception,
                # the extraction code is correctly called again
                shutil.rmtree(self._extracted_source_jar_dir, ignore_errors=True)
                raise

        return self._extracted_source_jar_dir

    def put_source_jar(self, source_jar_path):
        """Upload source jar to the remote S3 bucket.

        :param source_jar_path: path to source jar to be uploaded
        """
        self._s3.store_file(source_jar_path, self._source_jar_object_key)

    def has_source_jar(self):
        """Test if the given EPV has source jar in the remote S3 bucket.

        :return: True if the given EPV has source jar in the remote S3 bucket
        """
        return self._s3.object_exists(self._source_jar_object_key)

    def get_sources(self):
        """Get path to source files.

        :return: path to source files
        """
        if not self._eco_obj:
            self._eco_obj = Ecosystem.by_name(self._postgres.session, self.ecosystem)

        if self._eco_obj.is_backed_by(EcosystemBackend.maven):
            return self.get_extracted_source_jar()
        else:
            return self.get_extracted_source_tarball()

    def has_sources(self):
        """Test if the given EPV has available sources.

        :return: true if the given EPV has available sources
        """
        if not self._eco_obj:
            self._eco_obj = Ecosystem.by_name(self._postgres.session, self.ecosystem)

        if self._eco_obj.is_backed_by(EcosystemBackend.maven):
            return self._s3.object_exists(self._source_jar_object_key)
        else:
            self._construct_source_tarball_names()
            return self._s3.object_exists(self._source_tarball_object_key)


class ObjectCache(object):
    """Artifact cache handling that encapsulates artifacts handling on worker side.

    >>> epv_cache = ObjectCache.get(ecosystem='npm', name='serve-static', version='1.7.1')
    >>> extracted_tarball_path = epv_cache.get_extracted_source_tarball()
    """

    _cache = {}
    _base_cache_dir = configuration.WORKER_DATA_DIR

    def __init__(self):
        """Raise error as the cache can not be instantiated."""
        raise NotImplementedError()

    @classmethod
    def wipe(cls):
        """Wipe all files that are stored in the current cache."""
        for item in cls._cache.values():
            item.remove_files()
        cls._cache = {}

    @classmethod
    def _cache_dir(cls, ecosystem, name, version):
        """Get cache dir for the given EPV."""
        return os.path.join(cls._base_cache_dir, ecosystem, name, version)

    @classmethod
    def get(cls, ecosystem, name, version):
        """Get EPVCache for the given EPV."""
        # This code just stores info about downloaded objects, once we will
        # want to optimize number of retrievals and do some caching, remove
        # wipe() call in the base task and implement caching logic here
        key = (ecosystem, name, version)
        if key not in cls._cache:
            cache_dir = cls._cache_dir(ecosystem, name, version)
            # Artifacts bucket used for caching can be expanded based on env variables
            item = EPVCache(ecosystem, name, version, cache_dir,
                            is_temporary=True if ecosystem == 'go' else False)
            cls._cache[key] = item
            return item
        else:
            return cls._cache[key]

    @classmethod
    def get_from_dict(cls, dictionary):
        """Sugar for self.get() that respects arguments from a dict."""
        return cls.get(dictionary['ecosystem'], dictionary['name'], dictionary['version'])
