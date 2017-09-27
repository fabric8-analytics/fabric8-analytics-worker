import logging
import requests
import functools

from f8a_worker.defaults import F8AConfiguration as configuration

logger = logging.getLogger(__name__)

# We treat the fact product names are stored elsewhere as an
# implementation detail of the Pulp CDN.
# Different SRPM releases are likely to end up in the same
# Red Hat Engineering products, so we cache those lookups
# TODO: Make this properly configurable
_RED_HAT_PRODUCT_API = 'http://servicejava.corp.qa.redhat.com/svcrest/product/v3/engproducts/'


@functools.lru_cache()
def _get_product_name(product_id, service_api=_RED_HAT_PRODUCT_API):
    query_url = _RED_HAT_PRODUCT_API + product_id
    response = requests.get(query_url)
    response.raise_for_status()
    data = response.json()['engProducts'][0]
    if data['status'] != 'ACTIVE':
        return None  # Hide inactive products
    return data['name']


# There are also Pulp bindings for Python (python2-pulp-bindings package on Fedora)
# https://github.com/pulp/pulp/tree/master/bindings/pulp/bindings
# We can use them once they are ported to Python 3

# Example usage:
# pulp = Pulp(pulp_url="https://pulp.xyz.com",
#             pulp_auth=('user', 'password'))
# for r in pulp.get_repositories_for_srpm('python-requests-2.6.0-3.el6.src.rpm'):
#    print("repository %s channels: %s" % (r, pulp.get_rhn_channels_for_repo(r)))
#    print("repository %s tps_stream: %s" % (r, pulp.get_tps_stream_for_repo(r)))
class Pulp(object):
    def __init__(self, pulp_url=None, pulp_auth=None, verify=None, cache_repositories=False):
        """
        :param pulp_url: str, url with scheme included
        :param pulp_auth: 2-tuple, (username, password)
        :param verify: str, CA_BUNDLE path
        :param cache_repositories: Fetch all repositories at once and store them
                                   in self.repositories as a dictionary (key is repo_id).
                                   It takes 25 seconds, but for rpms which are in many repositories
                                   querying them individually may take even few times longer.
        """
        self.pulp_url = pulp_url or configuration.PULP_URL
        if not self.pulp_url:
            raise ValueError('No Pulp url specified')
        self.auth = pulp_auth or (configuration.PULP_USERNAME,
                                  configuration.PULP_PASSWORD)
        self.verify = verify or '/etc/pki/tls/certs/ca-bundle.crt'
        self.cache_repositories = cache_repositories
        self.repositories = None

    def query_pulp_api(self, api_path):
        if not self.pulp_url:
            logger.error('No Pulp url specified')
            return None
        url = self.pulp_url + api_path
        logger.debug('GET %s' % url)
        return requests.get(url, auth=self.auth, verify=self.verify)

    def post_pulp_api(self, api_path, data):
        if not self.pulp_url:
            logger.error('No Pulp url specified')
            return None
        url = self.pulp_url + api_path
        logger.debug('POST %s to %s' % (data, url))
        return requests.post(url, json=data, auth=self.auth, verify=self.verify)

    def get_content_units_for_srpm(self, srpm_filename):
        """
        :param srpm_filename: str, e.g. "nodejs-express-4.13.3-4.el7.src.rpm"
        :return: list of dicts
        """
        api_path = "/pulp/api/v2/content/units/rpm/search/"
        data = {'criteria': {'fields': [],
                             'filters': {'sourcerpm': srpm_filename}},
                'include_repos': True}
        response = self.post_pulp_api(api_path, data)

        if response is None or response.status_code != requests.codes.ok:
            logger.error("POST to Pulp %s failed" % api_path)
            return []

        content_units = response.json()
        logger.debug("content_units: %s", content_units)
        if not isinstance(content_units, list):
            logger.error("%s response is not a list: %s" % (api_path, content_units))
            return []

        return content_units

    def get_repositories_for_srpm(self, srpm_filename):
        """

        :param srpm_filename: str
        :return: list of repository ids (str)
        """
        content_units = self.get_content_units_for_srpm(srpm_filename)
        repo_ids = []
        for cu in content_units:
            repo_ids = repo_ids + cu.get("repository_memberships", [])
        return sorted(set(repo_ids))

    def get_repositories(self):
        """
        :return: list of all repositories
        """
        api_path = "/pulp/api/v2/repositories/"
        response = self.query_pulp_api(api_path)

        if response is None or response.status_code != requests.codes.ok:
            logger.error("query Pulp %s failed" % api_path)
            return {}

        repositories = response.json()
        if not isinstance(repositories, list):
            logger.error("%s response is not a list: %s" % (api_path, repositories))
            return []

        return repositories

    def get_repository(self, repo_id):
        """
        :param repo_id: str, e.g. "rhel-7-desktop-htb-isos__x86_64"
        :return: dict
        """
        if self.cache_repositories:
            if self.repositories is None:
                repos_list = self.get_repositories()
                repos_dict = {repo['display_name']: repo for repo in repos_list}
                self.repositories = repos_dict
            try:
                repository = self.repositories[repo_id]
            except KeyError:
                logger.error("no %s in cached repositories" % repo_id)
                return {}
            return repository

        api_path = "/pulp/api/v2/repositories/" + repo_id + "/"
        response = self.query_pulp_api(api_path)

        if response is None or response.status_code != requests.codes.ok:
            logger.error("query Pulp %s failed" % api_path)
            return {}

        repository = response.json()
        if not isinstance(repository, dict):
            logger.error("%s response is not a dict: %s" % (api_path, repository))
            return {}

        return repository

    def get_cdn_fields_for_repo(self, repo_id, fields):
        """Retrieves metadata fields from the given repo

        For consistency of handling, all fields are treated as comma-separated.

        For example, given:

            repo_id = "rhel-6-workstation-source-rpms__6Workstation__x86_64"
            fields = ["eng_product", "content_set", "rhn_channels"]

        The result will be:

        {
            "eng_product": ["71"]
            "content_set": ["rhel-6-workstation-source-rpms"]
            "rhn_channels": ["rhel-x86_64-workstation-6",
                             "rhel-x86_64-workstation-6-debuginfo"]
        }
        """
        repository = self.get_repository(repo_id)
        repo_notes = repository.get("notes", {})
        result = {}
        for field in fields:
            raw_value = repo_notes.get(field, "")
            # Assume comma-separated list even for single-valued fields
            result[field] = [entry for entry in raw_value.split(",") if entry]
        return result

    def _get_product_name(self, product_id):
        """Helper to convert Red Hat product IDs to product names"""
        return _get_product_name(product_id)

    def get_cdn_metadata_for_srpm(self, srpm_filename):
        """Returns a mapping with key CDN metadata for an SRPM:

        "srpm_filename": the supplied SRPM filename
        "rhsm_product_names": Names of Engineering products including the SRPM
        "rhsm_content_sets": RHSM Content Sets that include the SRPM
        "rhn_channels": Legacy RHN Channels that include the SRPM
        """
        query_fields = ("eng_product", "content_set", "rhn_channels")
        engineering_product_ids = set()
        rhn_channels = set()
        rhsm_content_sets = set()
        for repo_id in self.get_repositories_for_srpm(srpm_filename):
            repo_data = self.get_cdn_fields_for_repo(repo_id, query_fields)
            engineering_product_ids.update(repo_data["eng_product"])
            rhn_channels.update(repo_data["rhn_channels"])
            rhsm_content_sets.update(repo_data["content_set"])
        maybe_names = map(self._get_product_name, engineering_product_ids)
        rhsm_product_names = (name for name in maybe_names if name is not None)
        return {
            "srpm_filename": srpm_filename,
            "rhsm_product_names": sorted(rhsm_product_names),
            "rhsm_content_sets": sorted(rhsm_content_sets),
            "rhn_channels": sorted(rhn_channels),
        }
