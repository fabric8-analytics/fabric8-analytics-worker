from bs4 import BeautifulSoup
import requests
import logging
from f8a_worker.base import BaseTask
from selinon import FatalTaskError


class GithubStats(BaseTask):
    """ Collects statistics by parsing Github Page """

    @classmethod
    def _get_page(cls, repo_name):
        github_url = 'https://github.com'
        url = github_url + repo_name
        raw_data = requests.get(url)
        if raw_data:
            soup = BeautifulSoup(raw_data.text, "html.parser")
            return soup
        else:
            self.log.info("Could not fetch the page for repo_name:"% repo_name)

    @classmethod
    def _get_stargazers(cls, soup, repo_name):
        stars_string =  soup.find(attrs={"href": repo_name + "/stargazers"})
        if stars_string is not None:
            stars_string1 = stars_string.text.strip()
            stars = int(stars_string1.replace(',',''))
            return stars
        else:
            return 0

    @classmethod
    def _get_watchers(cls, soup, repo_name):
        watches_string =soup.find(attrs={"href": repo_name + "/watchers"})
        if watches_string is not None:
            watches_string1 = watches_string.text.strip()
            watches = int(watches_string1.replace(',',''))
            return watches
        else:
            return 0

    @classmethod
    def _get_fork_count(cls, soup, repo_name):
        forks_string = soup.find(attrs={"href": repo_name + "/network"})
        if forks_string is not None:
            forks_string1 = forks_string.text.strip()
            forks = int(forks_string1.replace(',',''))
            return forks
        else:
            return 0

    @classmethod
    def execute(cls, arguments):
        self._strict_assert(arguments.get('repo_name'))
        self._strict_assert(arguments.get('ecosystem'))
        repo_name_passed = arguments.get('repo_name')
        repo_name = "/" + repo_name_passed
        ecosystem = arguments.get("ecosystem")
        soup = cls._get_page(repo_name)
        if soup is not None:
            github_stats = {
                "stars": cls._get_stargazers(soup, repo_name),
                "forks": cls._get_fork_count(soup, repo_name),
                "watches": cls._get_watchers(soup, repo_name),
                "repo_name": repo_name_passed,
                "ecosystem": ecosystem
            }
            return github_stats
        else:
            raise FatalTaskError("No Github Statistics is found for repo_name: {} wirh task_d: {}".
                                                                    format(repo_name, self.task_id))
        return
