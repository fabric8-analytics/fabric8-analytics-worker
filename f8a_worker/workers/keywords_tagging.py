"""Perform keywords lookup on texts collected and available."""

import requests
from tempfile import NamedTemporaryFile
from contextlib import contextmanager
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
    _UPDATE_TIME = timedelta(minutes=15)
    _TAGS_URL = 'https://raw.githubusercontent.com/fabric8-analytics/' \
                'fabric8-analytics-tags/master/{ecosystem}_tags.yaml'

    # Configuration of f8a_tagger lookup function - additional options. See f8a_tagger implementation for more details
    _LOOKUP_CONF = {
        'lemmatize': True,
        'stemmer': 'EnglishStemmer',
        'ignore_errors': False,
        'ngram_size': None
    }

    @contextmanager
    def _get_keywords_yaml(self, ecosystem):
        """Download keywords.yaml file if update time expires, otherwise use cached one.

        :param ecosystem: ecosystem for which keywords file should be retrieved
        :return: keywords.yaml file as stored on GitHub
        """
        if self._keywords_yaml.get(ecosystem) is None \
                or self._keywords_yaml_update[ecosystem] + self._UPDATE_TIME < datetime.now():
            self.log.info("Updating keywords.yaml file for ecosystem '%s'", ecosystem)

            response = requests.get(self._TAGS_URL.format(ecosystem=ecosystem))
            if response.status_code != 200:
                raise RuntimeError("Unable to download keywords.yaml file for ecosystem '%s', HTTP status code is %s"
                                   % (ecosystem, response.status_code))

            if ecosystem in self._keywords_yaml:
                self._keywords_yaml[ecosystem].close()

            fp = NamedTemporaryFile('r+', delete=False)
            fp.write(response.text)
            fp.close()

            self._keywords_yaml[ecosystem] = fp.name
            self._keywords_yaml_update[ecosystem] = datetime.now()
            self.log.info("File keywords.yaml file for ecosystem '%s'", ecosystem)

        yield self._keywords_yaml[ecosystem]

    def execute(self, arguments):
        # Keep f8a_tagger import local as other components dependent on f8a_worker do not require it installed.
        from f8a_tagger import lookup_readme as keywords_lookup_readme
        from f8a_tagger import lookup_tetxt as keywords_lookup_text

        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        ecosystem = arguments['ecosystem']
        name = arguments['name']

        details = {}
        with self._get_keywords_yaml(ecosystem) as keywords_file_name:
            if 'metadata' in self.parent.keys():
                self._strict_assert(arguments.get('version'))

                details['description'] = []
                metadata = self.parent_task_result('metadata')
                description = metadata.get('details', [{}])[0].get('description', '')
                self.log.debug("Computing keywords from description: '%s'", description)
                details['description'] = keywords_lookup_text(description, keywords_file=keywords_file_name,
                                                              **self._LOOKUP_CONF)

                # explicitly gather declared keywords by publisher
                self.log.debug("Aggregating explicitly stated keywords by publisher")
                details['keywords'] = metadata.get('details', [{}])[0].get('keywords')

            if 'GitReadmeCollectorTask' in self.parent.keys():
                s3 = StoragePool.get_connected_storage('S3Readme')
                readme_json = s3.retrieve_readme_json(ecosystem, name)
                self.log.debug("Computing keywords from README.json")
                details['README'] = keywords_lookup_readme(readme_json, keywords_file=keywords_file_name,
                                                           **self._LOOKUP_CONF)

        return {'status': 'success', 'summary': [], 'details': details}
