"""Class to gather package description available in repository."""

import requests
from bs4 import BeautifulSoup
from f8a_worker.base import BaseTask
from f8a_worker.errors import NotABugFatalTaskError
from selinon import FatalTaskError


class RepositoryDescCollectorTask(BaseTask):
    """Gather package description available in repository."""

    add_audit_info = False

    _NPM_PACKAGE_URL = 'https://www.npmjs.com/package/{package}'
    _PYPI_PACKAGE_URL = 'https://pypi.org/project/{package}'

    @staticmethod
    def _scrape_page(url):
        """Web scrape URL."""
        response = requests.get(url)
        if response.status_code != 200:
            raise NotABugFatalTaskError("Unable to access package web page at '%s'" % url)
        return BeautifulSoup(response.text, 'lxml')

    def collect_npm(self, name):
        """Collect plain text description from npmjs.com for the given package.

        :param name: package name for which the plain text description should be gathered
        :return: plain text description
        """
        url = self._NPM_PACKAGE_URL.format(package=name)
        content = self._scrape_page(url).body

        if not content:
            raise NotABugFatalTaskError("No content was found at '%s' for NPM package '%s'", name)

        # rip out all script and style elements
        for script in content(["script", "style"]):
            script.extract()

        return content.text

    def collect_pypi(self, name):
        """Collect plain text description from PyPI for the given package.

        :param name: package name for which the plain text description should be gathered
        :return: plain text description
        """
        url = self._PYPI_PACKAGE_URL.format(package=name)
        content = self._scrape_page(url).find(class_='project-description')

        if not content:
            raise NotABugFatalTaskError("No content was found at '%s' for PyPI package '%s'", name)

        # Remove content that is automatically added by PyPI - this content is
        # on the bottom and keeps info extracted from setup.py. We already keep
        # this data, so remove duplicity in fact.
        nodot = content.find(class_='nodot')
        if nodot:
            nodot.decompose()
        return content.text

    _COLLECTOR_HANDLERS = {
        'npm': collect_npm,
        'maven': None,
        'pypi': collect_pypi,
        'nuget': None
    }

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        collector = self._COLLECTOR_HANDLERS.get(arguments['ecosystem'])

        if not collector:
            raise FatalTaskError("No repository description collector registered for ecosystem '%s'"
                                 % arguments['ecosystem'])

        # TODO: we should probably do some additional post-processing later
        return collector(self, arguments['name'])
