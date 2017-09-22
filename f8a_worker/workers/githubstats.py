from bs4 import BeautifulSoup
import requests
import logging
from f8a_worker.base import BaseTask

logger = logging.getLogger(__name__)

class GithubStats(BaseTask):
    """ Collects statistics by parsing Github Page """
    _analysis_name = "github_manifest_details"

    @classmethod
    def _get_page(cls, repo_name):
        github_url = 'https://github.com/'
        url = github_url + "/" + repo_name
        raw_data = requests.get(url)
        if raw_data:
            soup = BeautifulSoup(raw_data.text, "html.parser")
            return soup
        else:
            logger.info("Could not fetch the page for repo_name:"% repo_name)

    @classmethod
    def _get_stargazers(cls, soup, repo_name):
        stars =  soup.find(attrs={"href": repo_name + "/" + "stargazers"})
        return (stars.text).strip() if stars is not None else 0

    @classmethod
    def _get_watchers(cls, soup, repo_name):
        watches =soup.find(attrs={"href": repo_name + "/" + "watchers"})
        return (watches.text).strip() if watches is not None else 0

    @classmethod
    def _get_fork_count(cls, soup, repo_name):
        forks = soup.find(attrs={"href": repo_name + "/" + "network"})
        return (forks.text).strip() if forks is not None else 0

    @classmethod
    def execute(cls, arguments):
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
            logger.info("No Github Statistics is found for repo_name: %s" %repo_name_passed)
        return
