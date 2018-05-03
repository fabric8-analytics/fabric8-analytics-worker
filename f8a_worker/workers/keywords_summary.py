"""Summarize keywords found for the given package."""

import operator
from f8a_worker.base import BaseTask
from selinon import StoragePool


class KeywordsSummaryTask(BaseTask):
    """Aggregate keywords computed, prioritize keywords different sources and threshold them."""

    # Assign different priority to different keywords sources.
    _README_PRIORITY = 0.2
    _REPOSITORY_DESCRIPTION_PRIORITY = 0.2
    _DESCRIPTION_PRIORITY = 0.7
    _KEYWORDS_PRIORITY = 1.0
    _PACKAGE_NAME_PRIORITY = 1.0
    _GH_TOPICS_PRIORITY = 1.0
    # Use this count of tags in the final array
    _TAGS_COUNT = 4

    def _get_package_version_level_keywords(self, ecosystem, name):
        """Retrieve all version level keywords for the given package."""
        result = {}
        postgres = StoragePool.get_connected_storage('BayesianPostgres')

        for version in postgres.get_analysed_versions(ecosystem, name):
            self.log.debug("Retrieving results of 'keywords_tagging' for version '%s'", version)
            task_result = postgres.get_latest_task_result(ecosystem, name, version,
                                                          'keywords_tagging')
            if task_result:
                result[version] = task_result.get('details', {})

        return result

    def _get_package_level_keywords(self, ecosystem, name):
        """Retrieve all package level keywords for the given package."""
        package_postgres = StoragePool.get_connected_storage('PackagePostgres')

        self.log.debug("Retrieving results of 'keywords_tagging' on package level")
        task_result = package_postgres.get_latest_task_result(ecosystem, name, 'keywords_tagging')
        return task_result.get('details', {}) if task_result else {}

    def _threshold_found_keywords(self, keywords):
        """Threshold found keywords based on keywords source priority and resulting count."""
        # TODO: reduce cyclomatic complexity
        readme_kw = {kw: s * self._README_PRIORITY
                     for kw, s in keywords.get('package', {}).get('README', {}).items()}
        repository_description_kw = {kw: s * self._REPOSITORY_DESCRIPTION_PRIORITY
                                     for kw, s in keywords.get('package', {}).get(
                                         'repository_description', {}).items()}
        # No weight on GitHub topics, assign priority directly (weight is 1)
        gh_topics = {kw: self._GH_TOPICS_PRIORITY
                     for kw in keywords.get('package', {}).get('gh_topics', [])}
        package_name_kw = {kw: s * self._PACKAGE_NAME_PRIORITY
                           for kw, s in keywords.get('package', {}).get('package_name', {}).items()}

        all_version_kw = {}
        for version_kw in keywords.get('versions', {}).values():
            for keyword, score in version_kw.get('description', {}).items():
                all_version_kw[keyword] = all_version_kw.get(keyword, 0) + \
                                          (score * self._DESCRIPTION_PRIORITY)

            for keyword in version_kw.get('keywords', []) or []:
                # keywords are not weighted when aggregation is done, assign 1 explicitly
                all_version_kw[keyword] = all_version_kw.get(keyword, 0) + \
                                          (1 * self._KEYWORDS_PRIORITY)

        result = {}
        for keyword, score in readme_kw.items():
            result[keyword] = result.get(keyword, 0) + score
        for keyword, score in repository_description_kw.items():
            result[keyword] = result.get(keyword, 0) + score
        for keyword, score in all_version_kw.items():
            result[keyword] = result.get(keyword, 0) + score
        for keyword, score in gh_topics.items():
            result[keyword] = result.get(keyword, 0) + score
        for keyword, score in package_name_kw.items():
            result[keyword] = result.get(keyword, 0) + score

        result = list(sorted(result.items(), key=operator.itemgetter(1), reverse=True))

        return {
            'result': result[:self._TAGS_COUNT],
            # we can get rid of this in the future, but keep it for debug info
            '_sorted': result
        }

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        result = {
            '_all': dict(
                package=self._get_package_level_keywords(arguments['ecosystem'],
                                                         arguments['name']),

                versions=self._get_package_version_level_keywords(arguments['ecosystem'],
                                                                  arguments['name'])
            )
        }

        result['tags'] = self._threshold_found_keywords(result['_all'])
        return result
