from bs4 import BeautifulSoup
from re import compile as re_compile
from requests import get

from f8a_worker.base import BaseTask
from f8a_worker.schemas import SchemaRef


class LibrariesIoTask(BaseTask):
    """ Collects statistics from Libraries.io """
    _analysis_name = "libraries_io"
    # schema_ref = SchemaRef(_analysis_name, '1-0-0')

    @staticmethod
    def _get_list_term_description(page, term_name):
        tag = page.find(string=re_compile(r'^\s*{}\s*$'.format(term_name)))
        return tag.find_next('dd')

    def _get_list_term_description_text(self, page, term_name):
        term_description = self._get_list_term_description(page, term_name)
        return term_description.text.strip()

    def _get_list_term_description_time(self, page, term_name):
        term_description = self._get_list_term_description(page, term_name)
        return term_description.find('time').get('datetime')

    def get_releases(self, page):
        latest_version = ''
        latest_published_at = ''
        recent = {}

        releases_tag = page.find_all('div', class_="col-md-4 sidebar")[-1]
        vers = releases_tag.find_all('dt')
        if vers:
            # Releases
            latest_version = vers[0].find('a').text.strip()
            latest_published_at = vers[0].find_next('dd').text.strip()
            recent = {v.find('a').text.strip(): v.find_next('dd').text.strip() for v in vers[1:]}
        else:
            # Tagged Releases, e.g. https://libraries.io/pypi/osbs-client/
            vers = releases_tag.find_all('dl')[1:]
            if vers:
                latest_version = vers[0].text.strip()
                latest_published_at = vers[0].find_next('dd').text.strip()
                recent = {v.text.strip(): v.find_next('dd').text.strip() for v in vers[1:]}

        releases = {'count': self._get_list_term_description_text(page, 'Total releases'),
                    'latest': {'version': latest_version,
                               'published_at': latest_published_at,
                               'recent': recent}}
        return releases

    def get_dependents(self, page):
        dependents = {'count': self._get_list_term_description_text(page, 'Dependent projects')}
        return dependents

    def get_dependent_repositories(self, page, top_dependent_repos_page):
        # dict of <repository>: <number of stars> from
        # https://libraries.io/{ecosystem}/{name}/top_dependent_repos
        top_dep_repos = {tag.text.strip(): tag.find_next('dd').text.strip()
                         for tag in top_dependent_repos_page.find_all(['dt'])}
        dependent_repos = {'count': self._get_list_term_description_text(page,
                                                                         'Dependent repositories'),
                           'top': top_dep_repos}
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
                   'dependents': self.get_dependents(page),
                   'dependent_repositories': self.get_dependent_repositories(page,
                                                                        top_dependent_repos_page)}

        return {'status': 'success',
                'summary': [],
                'details': details}
