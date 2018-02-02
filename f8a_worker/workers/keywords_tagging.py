"""Perform keywords lookup on texts collected and available."""

import os
import re
import requests
from tempfile import NamedTemporaryFile
from datetime import timedelta
from datetime import datetime

from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef
from selinon import StoragePool


class KeywordsTaggingTaskBase(BaseTask):
    """Base task for keywords tagging tasks."""

    # keywords.yaml files are ecosystem specific, keep them for _UPDATE_TIME -
    # once _UPDATE_TIME expires update them directly from GitHub
    _keywords_yaml = {}
    _keywords_yaml_update = {}
    _UPDATE_TIME = timedelta(minutes=30)
    _stopwords_txt = None
    _stopwords_txt_update = None
    _TAGS_URL = 'https://raw.githubusercontent.com/fabric8-analytics/' \
                'fabric8-analytics-tags/master/{ecosystem}_tags.yaml'
    _STOPWORDS_URL = 'https://raw.githubusercontent.com/fabric8-analytics/' \
                     'fabric8-analytics-tags/master/stopwords.txt'

    # Configuration of f8a_tagger lookup function - additional options. See
    # f8a_tagger implementation for more details
    _LOOKUP_CONF = {
        'lemmatize': True,
        'stemmer': 'EnglishStemmer',
        'ngram_size': None,
        'scorer': 'RelativeUsage'
    }

    def _get_keywords_yaml(self, ecosystem):
        """Download keywords.yaml file for the given ecosystem, use cached one if needed.

        :param ecosystem: ecosystem for which keywords.yaml file should be downloaded
        :return: filename of downloaded keywords.yaml file
        """
        if self._keywords_yaml.get(ecosystem) is None \
                or self._keywords_yaml_update[ecosystem] < datetime.utcnow():
            self.log.info("Updating keywords.yaml file for ecosystem '%s'", ecosystem)

            response = requests.get(self._TAGS_URL.format(ecosystem=ecosystem))
            if response.status_code != 200:
                raise RuntimeError("Unable to download keywords.yaml file for ecosystem '%s', "
                                   "HTTP status code is %s"
                                   % (ecosystem, response.status_code))

            if ecosystem in self._keywords_yaml:
                os.remove(self._keywords_yaml[ecosystem])

            fp = NamedTemporaryFile('r+', delete=False)
            fp.write(response.text)
            fp.close()

            self._keywords_yaml[ecosystem] = fp.name
            self._keywords_yaml_update[ecosystem] = datetime.utcnow() + self._UPDATE_TIME
            self.log.info("Downloaded file keywords.yaml for ecosystem '%s'", ecosystem)

        return self._keywords_yaml[ecosystem]

    def _get_stopwords_txt(self):
        """Get stopwords.txt file, use cached one if available.

        :return: filename of downloaded stopwords.txt file
        """
        if self._stopwords_txt is None \
                or self._stopwords_txt_update < datetime.utcnow():
            self.log.debug("Updating stopwords.txt file")

            response = requests.get(self._STOPWORDS_URL)
            if response.status_code != 200:
                raise RuntimeError("Unable to download stopwords.txt file, HTTP status code is %s"
                                   % response.status_code)

            if self._stopwords_txt is not None:
                os.remove(self._stopwords_txt)

            fp = NamedTemporaryFile('r+', delete=False)
            fp.write(response.text)
            fp.close()

            self._stopwords_txt = fp.name
            self._stopwords_txt_update = datetime.utcnow() + self._UPDATE_TIME
            self.log.info("Downloaded stopwords.txt file")

        return self._stopwords_txt

    def _get_config_files(self, ecosystem):
        """Download keywords.yaml and stopwords.txt files if update time expires.

        The cached ones are used otherwise.

        :param ecosystem: ecosystem for which config files should be retrieved
        :return: tuple with keywords.yaml and stopwords.txt file as stored on GitHub
        """
        keywords_yaml = self._get_keywords_yaml(ecosystem)
        stopwords_txt = self._get_stopwords_txt()
        return keywords_yaml, stopwords_txt

    def execute(self, arguments):
        raise NotImplementedError("Please derive from base task for specific tagging tasks")


class KeywordsTaggingTask(KeywordsTaggingTaskBase):
    """Compute tags based on gathered natural text - package-version level keywords."""

    _analysis_name = 'keywords_tagging'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def _package_version_level_keywords(self, keywords_file_name, stopwords_file_name, arguments):
        # Keep f8a_tagger import local as other components dependent on
        # f8a_worker do not require it installed.
        from f8a_tagger import lookup_text as keywords_lookup_text

        details = {}
        if 'metadata' in self.parent.keys():
            details['description'] = {}
            metadata = self.parent_task_result('metadata')
            description = metadata.get('details', [{}])[0].get('description', '')
            if description:
                self.log.debug("Computing keywords from description: '%s'", description)
                details['description'] = keywords_lookup_text(description,
                                                              keywords_file=keywords_file_name,
                                                              stopwords_file=stopwords_file_name,
                                                              **self._LOOKUP_CONF)

            # explicitly gather declared keywords by publisher
            self.log.debug("Aggregating explicitly stated keywords by publisher")
            details['keywords'] = metadata.get('details', [{}])[0].get('keywords', [])

        return details

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        keywords_file_name, stopwords_file_name = self._get_config_files(arguments['ecosystem'])
        details = self._package_version_level_keywords(keywords_file_name, stopwords_file_name,
                                                       arguments)

        return {'status': 'success', 'summary': [], 'details': details}


class PackageKeywordsTaggingTask(KeywordsTaggingTaskBase):
    """Compute tags based on gathered natural text - strictly package level keywords."""

    _analysis_name = 'package_keywords_tagging'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    def _package_level_keywords(self, keywords_file_name, stopwords_file_name, arguments):
        # Keep f8a_tagger import local as other components dependent on
        # f8a_worker do not require it installed.
        from f8a_tagger import lookup_readme as keywords_lookup_readme
        from f8a_tagger import lookup_text as keywords_lookup_text

        details = {}
        package_postgres = StoragePool.get_connected_storage('PackagePostgres')

        gh_info = package_postgres.get_task_result_by_analysis_id(arguments['ecosystem'],
                                                                  arguments['name'],
                                                                  'github_details',
                                                                  arguments['document_id'])
        if gh_info:
            self.log.debug("Aggregating explicitly stated keywords (topics) on GitHub")
            details['gh_topics'] = gh_info.get('details', {}).get('topics', [])

        s3_readme = StoragePool.get_connected_storage('S3Readme')
        try:
            readme_json = s3_readme.retrieve_readme_json(arguments['ecosystem'], arguments['name'])
            if readme_json:
                self.log.debug("Computing keywords from README.json")
                details['README'] = keywords_lookup_readme(readme_json,
                                                           keywords_file=keywords_file_name,
                                                           stopwords_file=stopwords_file_name,
                                                           **self._LOOKUP_CONF)
        except Exception as exc:
            self.log.info("Failed to retrieve README: %s", str(exc))

        s3_rd = StoragePool.get_connected_storage('S3RepositoryDescription')
        try:
            description = s3_rd.retrieve_repository_description(arguments['ecosystem'],
                                                                arguments['name'])
            if description:
                self.log.debug("Computing keywords on description from repository")
                details['repository_description'] = keywords_lookup_text(
                    description,
                    keywords_file=keywords_file_name,
                    stopwords_file=stopwords_file_name,
                    **self._LOOKUP_CONF)

        except Exception as exc:
            self.log.info("Failed to retrieve repository description: %s", str(exc))

        if self.task_name == 'package_keywords_tagging':
            # We are tagging on package level, add also tags that are found in package name
            name_parts = re.split('[\.\-_:]', arguments['name'])
            self.log.debug("Computing keywords from package name %s", name_parts)
            details['package_name'] = keywords_lookup_text(" ".join(name_parts),
                                                           keywords_file=keywords_file_name,
                                                           stopwords_file=stopwords_file_name,
                                                           **self._LOOKUP_CONF)

        return details

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        keywords_file_name, stopwords_file_name = self._get_config_files(arguments['ecosystem'])
        details = self._package_level_keywords(keywords_file_name, stopwords_file_name,
                                               arguments)

        return {'status': 'success', 'summary': [], 'details': details}
