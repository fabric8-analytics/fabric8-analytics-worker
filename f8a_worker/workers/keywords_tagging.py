"""Perform keywords lookup on texts collected and available."""

import os
import requests
from tempfile import NamedTemporaryFile
from datetime import timedelta
from datetime import datetime

from f8a_worker.base import BaseTask
from selinon import StoragePool

# from f8a_worker.schemas import SchemaRef


class KeywordsTaggingTask(BaseTask):
    """Compute tags based on gathered natural text."""
    _analysis_name = 'keywords_tagging'
    # schema_ref = SchemaRef(_analysis_name, '1-0-0')

    # keywords.yaml files are ecosystem specific, keep them for _UPDATE_TIME - once _UPDATE_TIME expires update
    # them directly from GitHub
    _keywords_yaml = {}
    _keywords_yaml_update = {}
    _UPDATE_TIME = timedelta(minutes=30)
    _stopwords_txt = None
    _stopwords_txt_update = None
    _TAGS_URL = 'https://raw.githubusercontent.com/fabric8-analytics/' \
                'fabric8-analytics-tags/master/{ecosystem}_tags.yaml'
    _STOPWORDS_URL = 'https://raw.githubusercontent.com/fabric8-analytics/' \
                     'fabric8-analytics-tags/master/stopwords.txt'

    # Configuration of f8a_tagger lookup function - additional options. See f8a_tagger implementation for more details
    _LOOKUP_CONF = {
        'lemmatize': True,
        'stemmer': 'EnglishStemmer',
        'ignore_errors': False,
        'ngram_size': None
    }

    def _get_keywords_yaml(self, ecosystem):
        """Download keywords.yaml file for the given ecosystem, use cached one if needed

        :param ecosystem: ecosystem for which keywords.yaml file should be downloaded
        :return: filename of downloaded keywords.yaml file
        """
        if self._keywords_yaml.get(ecosystem) is None \
                or self._keywords_yaml_update[ecosystem] < datetime.now():
            self.log.info("Updating keywords.yaml file for ecosystem '%s'", ecosystem)

            response = requests.get(self._TAGS_URL.format(ecosystem=ecosystem))
            if response.status_code != 200:
                raise RuntimeError("Unable to download keywords.yaml file for ecosystem '%s', HTTP status code is %s"
                                   % (ecosystem, response.status_code))

            if ecosystem in self._keywords_yaml:
                os.remove(self._keywords_yaml[ecosystem])

            fp = NamedTemporaryFile('r+', delete=False)
            fp.write(response.text)
            fp.close()

            self._keywords_yaml[ecosystem] = fp.name
            self._keywords_yaml_update[ecosystem] = datetime.now() + self._UPDATE_TIME
            self.log.info("Downloaded file keywords.yaml for ecosystem '%s'", ecosystem)

        return self._keywords_yaml[ecosystem]

    def _get_stopwords_txt(self):
        """Get stopwords.txt file, use cached one if available.

        :return: filename of downloaded stopwords.txt file
        """
        if self._stopwords_txt is None \
                or self._stopwords_txt_update < datetime.now():
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
            self._stopwords_txt_update = datetime.now() + self._UPDATE_TIME
            self.log.info("Downloaded stopwords.txt file")

        return self._stopwords_txt

    def _get_config_files(self, ecosystem):
        """Download keywords.yaml and stopwords.txt files if update time expires, otherwise use cached ones.

        :param ecosystem: ecosystem for which config files should be retrieved
        :return: tuple with keywords.yaml and stopwords.txt file as stored on GitHub
        """
        keywords_yaml = self._get_keywords_yaml(ecosystem)
        stopwords_txt = self._get_stopwords_txt()
        return keywords_yaml, stopwords_txt

    def execute(self, arguments):
        # Keep f8a_tagger import local as other components dependent on f8a_worker do not require it installed.
        from f8a_tagger import lookup_readme as keywords_lookup_readme
        from f8a_tagger import lookup_text as keywords_lookup_text

        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        ecosystem = arguments['ecosystem']
        name = arguments['name']

        details = {}
        keywords_file_name, stopwords_file_name = self._get_config_files(ecosystem)
        if 'metadata' in self.parent.keys():
            self._strict_assert(arguments.get('version'))

            details['description'] = []
            metadata = self.parent_task_result('metadata')
            description = metadata.get('details', [{}])[0].get('description', '')
            self.log.debug("Computing keywords from description: '%s'", description)
            details['description'] = keywords_lookup_text(description,
                                                          keywords_file=keywords_file_name,
                                                          stopwords_file=stopwords_file_name,
                                                          **self._LOOKUP_CONF)

            # explicitly gather declared keywords by publisher
            self.log.debug("Aggregating explicitly stated keywords by publisher")
            details['keywords'] = metadata.get('details', [{}])[0].get('keywords')

        if 'GitReadmeCollectorTask' in self.parent.keys():
            s3 = StoragePool.get_connected_storage('S3Readme')
            readme_json = s3.retrieve_readme_json(ecosystem, name)
            self.log.debug("Computing keywords from README.json")
            details['README'] = keywords_lookup_readme(readme_json,
                                                       keywords_file=keywords_file_name,
                                                       stopwords_file=stopwords_file_name,
                                                       **self._LOOKUP_CONF)

        return {'status': 'success', 'summary': [], 'details': details}
