"""Task to collects statistics from Libraries.io."""

from operator import itemgetter
from urllib.parse import quote

from f8a_worker.base import BaseTask
from f8a_worker.utils import get_response
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """Collects statistics from Libraries.io."""
    _analysis_name = "libraries_io"
    schema_ref = SchemaRef(_analysis_name, '2-0-0')

    def project_url(self, ecosystem, name):
        """Construct url to endpoint, which gets information about a project and it's versions."""
        url = '{api}/{platform}/{name}'.\
            format(api=self.configuration.LIBRARIES_IO_API,
                   platform=ecosystem,
                   name=name)

        # 'no-token' value forces the API call to not use ANY token.
        # It works, but if abused, they can cut our IP off,
        # therefore we use this only in tests.
        if self.configuration.LIBRARIES_IO_TOKEN and \
                self.configuration.LIBRARIES_IO_TOKEN != 'no-token':
            url += '?api_key=' + self.configuration.LIBRARIES_IO_TOKEN

        return url

    @staticmethod
    def recent_releases(versions, count=10):
        """Sort versions by 'published_at' and return 'count' latest."""
        return sorted(versions, key=itemgetter('published_at'))[-count:]

    def execute(self, arguments):
        """Task entrypoint."""
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        name = arguments['name']
        ecosystem = arguments['ecosystem']
        if ecosystem == 'go':
            name = quote(name, safe='')

        project = get_response(self.project_url(ecosystem, name))
        versions = project['versions']
        details = {'dependent_repositories': {'count': project['dependent_repos_count']},
                   'dependents': {'count': project['dependents_count']},
                   'releases': {'count': len(versions),
                                'recent': self.recent_releases(versions)
                                }
                   }

        return {'status': 'success',
                'summary': [],
                'details': details}
