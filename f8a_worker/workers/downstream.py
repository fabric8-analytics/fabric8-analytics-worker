"""
Queries Red Hat's internal toolchain for downstream usage metadata
"""
import anymarkup
import requests
import json
import os

from f8a_worker.base import BaseTask
from f8a_worker.enums import EcosystemBackend
from f8a_worker.errors import TaskError
from f8a_worker.models import Ecosystem
from f8a_worker.pulp import Pulp
from f8a_worker.schemas import SchemaRef
from f8a_worker.utils import TimedCommand, MavenCoordinates
from f8a_worker.workers.anitya import RH_MVN_DISTRO_NAME, RH_MVN_GA_REPO, RH_RPM_DISTRO_NAME


# Test hook: the worker tests mock this out,
# while integration tests provide a full Anitya instance
def _query_anitya_url(host_url, api_path):
    return requests.get(host_url + api_path)


class DownstreamUsageTask(BaseTask):
    """Queries Red Hat's internal toolchain for downstream component usage

    - queries Anitya for downstream package names
    - uses the package name and component version to query:
      - Brew for internal SRPM and build details
      - the Pulp CDN for redistribution details
    """
    _analysis_name = 'redhat_downstream'
    schema_ref = SchemaRef(_analysis_name, '2-2-1')

    _backend_to_anitya_ecosystem = {
        EcosystemBackend.npm: 'npm',
        EcosystemBackend.maven: 'maven',
        EcosystemBackend.pypi: 'pypi',
        EcosystemBackend.rubygems: 'rubygems',
        EcosystemBackend.nuget: 'nuget'
    }

    _ecosystem_to_prefix = {
        'npm': 'nodejs',
        'pypi': 'python',
        'rubygems': 'rubygem'
    }

    # Give CLI 10 minutes to retrieve results
    _BREWUTILS_CLI_TIMEOUT = 600

    def _get_artifact_hash(self, algorithm=None):
        wr = self.parent_task_result('digests')
        if wr:
            for details in wr['details']:
                if details.get('artifact'):
                    return details[algorithm or 'md5']
        return None

    @staticmethod
    def _prefix_package_name(name, ecosystem):
        prefix = DownstreamUsageTask._ecosystem_to_prefix.get(ecosystem, '')
        if prefix:
            return '{p}-{n}'.format(p=prefix, n=name)

        return name

    def _fetch_anitya_project(self, ecosystem, package):
        eco_model = self.storage.get_ecosystem(ecosystem)
        backend = self._backend_to_anitya_ecosystem.get(eco_model.backend, None)
        if backend is None:
            raise ValueError('Don\'t know how to add ecosystem {e} with backend {b} to Anitya'.
                             format(e=ecosystem, b=eco_model.backend))
        api_path = '/api/by_ecosystem/{e}/{p}/'.format(e=ecosystem, p=package)
        anitya_url = self.configuration.ANITYA_URL
        try:
            return _query_anitya_url(anitya_url, api_path)
        except (requests.HTTPError, requests.ConnectionError):
            msg = 'Failed to contact Anitya server at {}'
            self.log.exception(msg.format(self.configuration.ANITYA_URL))
        return None

    def _get_cdn_metadata(self, srpm_filename):
        """Try to retrieve Pulp CDN metadata"""
        try:
            pulp = Pulp()
        except ValueError as e:
            self.log.error(e)
            return None
        try:
            metadata = pulp.get_cdn_metadata_for_srpm(srpm_filename)
        except Exception as e:
            self.log.exception(e)
            return None
        return metadata

    def _add_mvn_results(self, result_summary, anitya_mvn_names, version):
        def _compare_version(downstream, upstream):
            dv = downstream
            if 'redhat' in dv:
                # remove ".redhat-X" or "-redhat-X" suffix
                dv = dv[:dv.find('redhat') - 1]
            if dv == upstream:
                return True
            else:
                return False

        downstream_rebuilds = []

        for name in anitya_mvn_names:
            ga = MavenCoordinates.from_str(name).to_repo_url(ga_only=True)
            metadata_url = '{repo}/{pkg}/maven-metadata.xml'.format(repo=RH_MVN_GA_REPO,
                                                                    pkg=ga)
            res = requests.get(metadata_url)
            if res.status_code != 200:
                self.log.info('Metadata for package {pkg} not found in {repo} (status {code})'.
                              format(pkg=name, repo=RH_MVN_GA_REPO, code=res.status_code))
                continue
            versions = anymarkup.parse(res.text)['metadata']['versioning']['versions']['version']
            # make sure 'versions' is a list (it's a string if there is just one version)
            if not isinstance(versions, list):
                versions = [versions]
            self.log.info('Found versions {v} for package {p}'.format(v=versions, p=name))
            for v in versions:
                if _compare_version(v, version):
                    downstream_rebuilds.append(v)

        result_summary['rh_mvn_matched_versions'] = downstream_rebuilds
        if downstream_rebuilds:
            # For now, we don't distinguish products, we just use general "Middleware"
            #  for all Maven artifacts
            result_summary['all_rhsm_product_names'].append('Middleware')

    @staticmethod
    def _is_inside_rh():
        """Returns True if running on RH network, False otherwise."""
        is_inside = False
        try:
            is_inside = int(os.environ.get("OPENSHIFT_DEPLOYMENT", 0)) == 0
        except ValueError:
            pass
        return is_inside

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        eco = arguments['ecosystem']
        pkg = arguments['name']
        tool_responses = {}
        result_summary = {
            'package_names': [],
            'registered_srpms': [],
            'all_rhn_channels': [],
            'all_rhsm_content_sets': [],
            'all_rhsm_product_names': []
        }
        result_data = {'status': 'error',
                       'summary': result_summary,
                       'details': tool_responses
                       }

        # bail out early; we need access to internal services or the package is
        # from Maven ecosystem, otherwise we can't comment on downstream usage
        is_maven = Ecosystem.by_name(self.storage.session, eco).is_backed_by(EcosystemBackend.maven)
        if not self._is_inside_rh() and not is_maven:
            return result_data

        self.log.debug('Fetching {e}/{p} from Anitya'.format(e=eco, p=pkg))
        res = self._fetch_anitya_project(eco, pkg)
        anitya_rpm_names = []
        anitya_mvn_names = []
        if res is None:
            result_data['status'] = 'error'
        elif res.status_code == 200:
            self.log.debug('Retrieved {e}/{p} from Anitya'.format(e=eco, p=pkg))
            anitya_response = res.json()
            tool_responses['redhat_anitya'] = anitya_response
            # For now, we assume all downstreams are ones we care about
            for entry in anitya_response['packages']:
                if entry['distro'] == RH_RPM_DISTRO_NAME:
                    anitya_rpm_names.append(entry['package_name'])
                elif entry['distro'] == RH_MVN_DISTRO_NAME:
                    anitya_mvn_names.append(entry['package_name'])
                else:
                    self.log.warning(
                        'Unknown distro {d} for downstream package {o} (package {p}) in Anitya'.
                        format(d=entry['distro'], o=entry['package_name'], p=pkg)
                    )
            self.log.debug('Candidate RPM names from Anitya: {}'.format(anitya_rpm_names))
            self.log.debug('Candidate MVN names from Anitya: {}'.format(anitya_mvn_names))
            # TODO: Report 'partial' here and switch to 'success' at the end
            result_data['status'] = 'success'
        else:
            msg = 'Failed to find Anitya project {e}/{p}. Anitya response: {r}'
            self.log.error(msg.format(e=eco, p=pkg, r=res.text))
            result_data['status'] = 'error'

        if self._is_inside_rh():
            # we have candidate downstream name mappings, check them against Brew
            seed_names = anitya_rpm_names or [self._prefix_package_name(pkg, eco)]
            self.log.debug('Checking candidate names in Brew: {}'.format(seed_names))

            args = ['brew-utils-cli', '--version', arguments['version']]
            artifact_hash = self._get_artifact_hash(algorithm='sha256')
            if artifact_hash:
                args += ['--digest', artifact_hash]
            args += seed_names

            self.log.debug("Executing command, timeout={timeout}: {cmd}".format(
                timeout=self._BREWUTILS_CLI_TIMEOUT,
                cmd=args))
            tc = TimedCommand(args)
            status, output, error = tc.run(timeout=self._BREWUTILS_CLI_TIMEOUT)
            self.log.debug("status = %s, error = %s", status, error)
            output = ''.join(output)
            self.log.debug("output = %s", output)
            if not output:
                raise TaskError("Error running command %s" % args)
            brew = json.loads(output)

            result_summary['package_names'] = brew['packages']
            result_summary['registered_srpms'] = brew['response']['registered_srpms']
            tool_responses['brew'] = brew['response']['brew']

            # we have SRPM details, fetch details on where the RPMs are shipped
            tool_responses['pulp_cdn'] = pulp_responses = []
            rhn_channels = set()
            rhsm_content_sets = set()
            rhsm_product_names = set()
            for srpm_summary in result_summary['registered_srpms']:
                srpm_filename = "{n}-{v}-{r}.src.rpm".format(n=srpm_summary['package_name'],
                                                             v=srpm_summary['version'],
                                                             r=srpm_summary['release'])
                cdn_metadata = self._get_cdn_metadata(srpm_filename)
                if cdn_metadata is None:
                    msg = 'Error getting shipping data for {e}/{p} SRPM: {srpm}'
                    self.log.error(msg.format(e=eco, p=pkg, srpm=srpm_filename))
                    continue
                pulp_responses.append(cdn_metadata)
                srpm_summary['published_in'] = cdn_metadata['rhsm_product_names']
                rhn_channels.update(cdn_metadata['rhn_channels'])
                rhsm_content_sets.update(cdn_metadata['rhsm_content_sets'])
                rhsm_product_names.update(cdn_metadata['rhsm_product_names'])
            result_summary['all_rhn_channels'] = sorted(rhn_channels)
            result_summary['all_rhsm_content_sets'] = sorted(rhsm_content_sets)
            result_summary['all_rhsm_product_names'] = sorted(rhsm_product_names)

        self._add_mvn_results(result_summary, anitya_mvn_names, arguments['version'])

        return result_data
