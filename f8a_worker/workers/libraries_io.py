from bs4 import BeautifulSoup
from requests import get

from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """ Collects statistics from Libraries.io """
    _analysis_name = "libraries_io"
    # schema_ref = SchemaRef(_analysis_name, '1-0-0')

    @staticmethod
    def _get_list_term_description(page, term_name):
        tag = page.find(string='\n{}\n'.format(term_name))
        text = tag.find_next('dd').text.strip()
        return text

    @staticmethod
    def _get_list_term_description_time(page, term_name):
        tag = page.find(string='\n{}\n'.format(term_name))
        time_tag = tag.find_next('dd').find('time')
        return time_tag['datetime']

    def get_releases(self, page):
        releases = {'count': self._get_list_term_description(page, 'Total releases'),
                    'latest': {'published_at': self._get_list_term_description_time(page,
                                                                               'Latest release')}}
        return releases

    def get_dependents(self, page, top_dependent_repos_page):
        top_stars_sum = sum([int(s.text.strip()) for s in
                             top_dependent_repos_page.find_all('dd', class_="col-xs-4")])
        dependents = {'count': self._get_list_term_description(page, 'Dependent projects'),
                      'stars': {'count': top_stars_sum}}
        return dependents

    def get_dependent_repositories(self, page):
        dependent_repos = {'count': self._get_list_term_description(page, 'Dependent repositories')}
        return dependent_repos

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        url = 'https://libraries.io/{ecosystem}/{name}'.format(ecosystem=arguments['ecosystem'],
                                                               name=arguments['name'])
        page = BeautifulSoup(get(url).text, 'html.parser')
        top_dependent_repos_page = BeautifulSoup(get(url+'/top_dependent_repos').text,
                                                 'html.parser')

        details = {'releases': self.get_releases(page),
                   'dependents': self.get_dependents(page, top_dependent_repos_page),
                   'dependent_repositories': self.get_dependent_repositories(page)}

        return {'status': 'success',
                'summary': [],
                'details': details}
