"""Task to collects statistics from Libraries.io."""

from bs4 import BeautifulSoup
from operator import itemgetter
from requests import get
from urllib.parse import quote

from f8a_worker.base import BaseTask
from f8a_worker.errors import TaskError
from f8a_worker.utils import get_response
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """Collects statistics from Libraries.io."""
    _analysis_name = "libraries_io"
    schema_ref = SchemaRef(_analysis_name, '2-0-0')

    @staticmethod
    def get_top_dependent_repositories(ecosystem, name):
        """Return content of https://libraries.io/{ecosystem}/{name}/top_dependent_repos as dict.

        There's no API equivalent of this page, but the page is very simple, we take
        everything from it and return as dict of <repository>: <number of stars>
        """
        url = 'https://libraries.io/{ecosystem}/{name}/top_dependent_repos'.\
            format(ecosystem=ecosystem, name=name)
        page = BeautifulSoup(get(url).text, 'html.parser')
        top_dep_repos = {tag.text.strip(): int(tag.find_next('dd').text.strip())
                         for tag in page.find_all(['dt'])}
        return top_dep_repos

    def project_url(self, ecosystem, name):
        """Construct url to endpoint, which gets information about a project and it's versions."""
        url = '{api}/{platform}/{name}?api_key={token}'.\
            format(api=self.configuration.LIBRARIES_IO_API,
                   platform=ecosystem,
                   name=name,
                   token=self.configuration.LIBRARIES_IO_TOKEN)
        return url

    @staticmethod
    def recent_releases(versions, count=10):
        """Sort versions by 'published_at' and return 'count' latest."""
        return sorted(versions, key=itemgetter('published_at'))[-count:]

    def execute(self, arguments):
        """Task entrypoint."""
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        result_data = {'status': 'unknown',
                       'summary': [],
                       'details': {}}

        name = arguments['name']
        ecosystem = arguments['ecosystem']
        if ecosystem == 'go':
            name = quote(name, safe='')

        try:
            project = get_response(self.project_url(ecosystem, name))
        except TaskError as e:
            self.log.debug(e)
            result_data['status'] = 'error'
            return result_data

        versions = project['versions']
        details = {'dependent_repositories': {'count': project['dependent_repos_count'],
                                              'top': self.get_top_dependent_repositories(ecosystem,
                                                                                         name)},
                   'dependents': {'count': project['dependents_count']},
                   'releases': {'count': len(versions),
                                # 'latest': {'version': project['latest_release_number'],
                                #           'published_at': project['latest_release_published_at']},
                                'recent': self.recent_releases(versions)
                                }
                   }

        return {'status': 'success',
                'summary': [],
                'details': details}
