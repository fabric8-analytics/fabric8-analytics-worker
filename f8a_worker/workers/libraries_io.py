"""Task to collects statistics from Libraries.io."""

from operator import itemgetter
from urllib.parse import quote

from f8a_worker.base import BaseTask
from f8a_worker.errors import TaskError
from f8a_worker.utils import get_response
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """Collects statistics from Libraries.io."""
    _analysis_name = "libraries_io"
    schema_ref = SchemaRef(_analysis_name, '2-0-0')

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
        details = {'dependent_repositories': {'count': project['dependent_repos_count']},
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
