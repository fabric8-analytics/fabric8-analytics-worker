"""Task to collects statistics from Libraries.io."""

from operator import itemgetter
from urllib.parse import quote

from selinon import StoragePool

from f8a_worker.base import BaseTask
from f8a_worker.models import Ecosystem
from f8a_worker.utils import get_response
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """Collects statistics from Libraries.io."""

    _analysis_name = "libraries_io"
    schema_ref = SchemaRef(_analysis_name, '2-0-0')

    @staticmethod
    def recent_releases(versions, count=10):
        """Sort versions by 'published_at' and return 'count' latest."""
        version_list = sorted(versions, key=itemgetter('published_at'))[-count:]
        for ver in version_list:
            if 'spdx_expression' in ver:
                del ver['spdx_expression']
            if 'original_license' in ver:
                del ver['original_license']
        return version_list

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        rdb_session = StoragePool.get_connected_storage('BayesianPostgres').session

        name = arguments['name']
        ecosystem = arguments['ecosystem']
        if ecosystem == 'go':
            name = quote(name, safe='')

        project_url = self.configuration.libraries_io_project_url(
            Ecosystem.by_name(rdb_session, ecosystem), name)
        project = get_response(project_url)
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
