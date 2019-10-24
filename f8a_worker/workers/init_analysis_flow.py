"""Initialize package-version level analysis."""

import os
import datetime
import shutil
import re
from selinon import FatalTaskError
from sqlalchemy.orm.exc import NoResultFound
from tempfile import mkdtemp

from f8a_worker.object_cache import ObjectCache
from f8a_worker.base import BaseTask
from f8a_worker.process import IndianaJones, MavenCoordinates
from f8a_worker.models import Analysis, EcosystemBackend, Ecosystem, Version, Package
from f8a_worker.utils import normalize_package_name
from f8a_utils.versions import get_versions_for_ep
from f8a_worker.errors import NotABugFatalTaskError


pattern = r'[\*Xx\-\>\=\<\~\^\|\/\:\+]'
pattern_ignore = re.compile(pattern)


class InitAnalysisFlow(BaseTask):
    """Download source and start whole analysis."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Input Arguments: {}".format(arguments))
        self._strict_assert(isinstance(arguments.get('ecosystem'), str))
        self._strict_assert(isinstance(arguments.get('name'), str))
        self._strict_assert(isinstance(arguments.get('version'), str))

        db = self.storage.session
        try:
            ecosystem = Ecosystem.by_name(db, arguments['ecosystem'])
        except NoResultFound:
            raise FatalTaskError('Unknown ecosystem: %r' % arguments['ecosystem'])

        # make sure we store package name in its normalized form
        arguments['name'] = normalize_package_name(ecosystem.backend.name, arguments['name'])

        if len(pattern_ignore.findall(arguments['version'])) > 0:
            self.log.info("Incorrect version alert {} {}".format(
                arguments['name'], arguments['version']))
            raise NotABugFatalTaskError("Incorrect version alert {} {}".format(
                arguments['name'], arguments['version']))

        # Dont try ingestion for private packages
        if get_versions_for_ep(arguments['ecosystem'], arguments['name']):
            self.log.info("Ingestion flow for {} {}".format(
                arguments['ecosystem'], arguments['name']))
        else:
            self.log.info("Private package ingestion ignored {} {}".format(
                arguments['ecosystem'], arguments['name']))
            raise NotABugFatalTaskError("Private package alert {} {}".format(
                arguments['ecosystem'], arguments['name']))

        p = Package.get_or_create(db, ecosystem_id=ecosystem.id, name=arguments['name'])
        v = Version.get_or_create(db, package_id=p.id, identifier=arguments['version'])

        if not arguments.get('force'):
            if db.query(Analysis).filter(Analysis.version_id == v.id).count() > 0:
                arguments['analysis_already_exists'] = True
                self.log.debug("Arguments returned by initAnalysisFlow without force: {}"
                               .format(arguments))
                return arguments

        cache_path = mkdtemp(dir=self.configuration.WORKER_DATA_DIR)
        epv_cache = ObjectCache.get_from_dict(arguments)

        try:
            if not epv_cache.\
                    has_source_tarball():
                _, source_tarball_path = IndianaJones.fetch_artifact(
                    ecosystem=ecosystem,
                    artifact=arguments['name'],
                    version=arguments['version'],
                    target_dir=cache_path
                )
                epv_cache.put_source_tarball(source_tarball_path)

            if ecosystem.is_backed_by(EcosystemBackend.maven):
                if not epv_cache.has_source_jar():
                    try:
                        source_jar_path = self._download_source_jar(cache_path, ecosystem,
                                                                    arguments)
                        epv_cache.put_source_jar(source_jar_path)
                    except Exception as e:
                        self.log.info(
                            'Failed to fetch source jar for maven artifact "{n}/{v}": {err}'.
                            format(n=arguments.get('name'),
                                   v=arguments.get('version'),
                                   err=str(e))
                        )

                if not epv_cache.has_pom_xml():
                    pom_xml_path = self._download_pom_xml(cache_path, ecosystem, arguments)
                    epv_cache.put_pom_xml(pom_xml_path)
        finally:
            # always clean up cache
            shutil.rmtree(cache_path)

        a = Analysis(version=v, access_count=1, started_at=datetime.datetime.utcnow())
        db.add(a)
        db.commit()

        arguments['document_id'] = a.id

        # export ecosystem backend so we can use it to easily control flow later
        arguments['ecosystem_backend'] = ecosystem.backend.name

        self.log.debug("Arguments returned by InitAnalysisFlow are: {}".format(arguments))
        return arguments

    @staticmethod
    def _download_source_jar(target, ecosystem, arguments):
        """Download sources jar."""
        artifact_coords = MavenCoordinates.from_str(arguments['name'])
        artifact_coords.packaging = 'jar'  # source is always jar even for war/aar etc.
        sources_classifiers = ['sources', 'src']

        if artifact_coords.classifier not in sources_classifiers:
            for sources_classifier in sources_classifiers:
                artifact_coords.classifier = sources_classifier
                try:
                    _, source_jar_path = IndianaJones.fetch_artifact(
                        ecosystem=ecosystem,
                        artifact=artifact_coords.to_str(omit_version=True),
                        version=arguments['version'],
                        target_dir=target
                    )
                except Exception:
                    if sources_classifier == sources_classifiers[-1]:
                        # fetching of all variants failed
                        raise
                else:
                    return source_jar_path

    @staticmethod
    def _download_pom_xml(target, ecosystem, arguments):
        """Download pom.xml."""
        artifact_coords = MavenCoordinates.from_str(arguments['name'])
        artifact_coords.packaging = 'pom'
        artifact_coords.classifier = ''  # pom.xml files have no classifiers

        IndianaJones.fetch_artifact(
            ecosystem=ecosystem,
            artifact=artifact_coords.to_str(omit_version=True),
            version=arguments['version'],
            target_dir=target
        )

        # pom has to be named precisely pom.xml, otherwise mercator's Java handler
        #  which uses maven as subprocess won't see it
        pom_xml_path = os.path.join(target, 'pom.xml')
        os.rename(
            os.path.join(target,
                         '{}-{}.pom'.format(artifact_coords.artifactId, arguments['version'])),
            pom_xml_path
        )
        return pom_xml_path
