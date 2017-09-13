"""
Adds project to Anitya, which will keep track of its latest version.
"""
import requests

from f8a_worker.conf import get_configuration
from f8a_worker.enums import EcosystemBackend
from f8a_worker.errors import TaskError
from f8a_worker.utils import DownstreamMapCache, MavenCoordinates
from f8a_worker.base import BaseTask

# name of "RPM" distro for Anitya
RH_RPM_DISTRO_NAME = 'rh-dist-git'
# name of "Maven" distro for Anitya
RH_MVN_DISTRO_NAME = 'rh-mvn'
RH_MVN_GA_REPO = 'https://maven.repository.redhat.com/ga'

configuration = get_configuration()


class AnityaTask(BaseTask):
    """Anitya task is responsible for making sure that given project from given ecosystem is
    tracked at used Anitya instance. If it is, nothing is done, else it is added there during
    the task execution.

    In future, we'll likely want to make this task also add upstream/downstream mapping
    to given project.

    The actual latest_version info is fetched dynamically:
    - f8a_worker.models.Analysis.latest_version is a dynamic property that does this
    - for the stack-info endpoint, we do this on API level for every component of the stack
    """
    _analysis_name = 'anitya'
    description = 'Adds project to Anitya to be tracked'
    _backend_to_anitya_ecosystem = {
        EcosystemBackend.npm: 'npm',
        EcosystemBackend.maven: 'maven',
        EcosystemBackend.pypi: 'pypi',
        EcosystemBackend.rubygems: 'rubygems',
        EcosystemBackend.nuget: 'nuget'
    }

    def _get_project_homepage(self, ecosystem, package):
        wr = self.parent_task_result('metadata')
        # Anitya requires homepage, so we must always return something
        # Anitya has uniqueness requirement on project + homepage, so make homepage project-unique
        homepage = None
        if wr:
            homepages =\
                [m.get("homepage") for m in wr.get('details', []) if m.get("homepage")]
            homepage = homepages[0] if homepages else None
        if homepage is not None:
            return homepage
        else:
            return configuration.anitya_url + \
                '/api/by_ecosystem/{e}/{p}'.format(e=ecosystem, p=package)

    def _get_artifact_hash(self, algorithm=None):
        wr = self.parent_task_result('digests')
        if wr:
            for details in wr['details']:
                if details.get('artifact'):
                    return details[algorithm or 'md5']
        return None

    def _create_anitya_project(self, ecosystem, package, homepage):
        eco_model = self.storage.get_ecosystem(ecosystem)
        backend = self._backend_to_anitya_ecosystem.get(eco_model.backend, None)
        if backend is None:
            raise ValueError('Don\'t know how to add ecosystem {e} with backend {b} to Anitya'.
                             format(e=ecosystem, b=eco_model.backend))
        url = configuration.anitya_url + '/api/by_ecosystem/' + backend
        data = {'ecosystem': backend, 'name': package, 'homepage': homepage, 'check_release': True}
        if backend == 'maven':
            # for Maven, Anitya needs to know "version_url", which is groupId:artifactId
            #   which is exactly what we use as package name
            data['version_url'] = package
        self.log.debug('Creating Anitya project: %s', data)
        return requests.post(url, json=data)

    def _add_downstream_mapping(self, ecosystem, upstream_project, distribution, package_name):
        anitya_url = configuration.anitya_url
        url = anitya_url + '/api/downstreams/{e}/{p}/'.format(e=ecosystem, p=upstream_project)
        downstream_data = {'distro': distribution, 'package_name': package_name}
        self.log.debug('Adding Anitya mapping: %s for %s/%s' % (downstream_data,
                                                              ecosystem,
                                                              upstream_project))
        return requests.post(url, json=downstream_data)

    def _get_downstream_rpm_pkgs(self, ecosystem, name):
        distro, packages, package_names = None, [], ''

        md5_hash = self._get_artifact_hash()
        eco_obj = self.storage.get_ecosystem(ecosystem)

        if eco_obj.is_backed_by(EcosystemBackend.maven):
            # for maven, we use 'maven' prefix, the mapping is:
            #   maven:groupId:artifactId => list,of,rpms
            #   we use the fact that for maven artifacts, the component name is groupId:artifactId
            hashmap = DownstreamMapCache()
            downstream_mapping = hashmap[name]
            if downstream_mapping is not None:
                try:
                    distro, package_names = downstream_mapping.split()
                except ValueError:
                    self.log.warning("Expecting 2 space-separated values, got '%s'",
                                     downstream_mapping)
            else:
                self.log.debug('No groupId:artifactId %s found in DB (dist-git)', name)
        elif md5_hash:
            # Here we assume that the artifact hash matches upstream.
            # In case of npm it's true as of npm-2.x.x in Fedora 24, but prior to that npm was
            # mangling downloaded tarballs. If that feature returns we probably need to change
            # IndianaJones to download artifacts directly.
            hashmap = DownstreamMapCache()
            downstream_mapping = hashmap[md5_hash]
            if downstream_mapping is not None:
                try:
                    distro, _, package_names = downstream_mapping.split()
                except ValueError:
                    self.log.warning("Expecting 3 space-separated values, got '%s'",
                                     downstream_mapping)
            else:
                self.log.debug('No hash %r found in DB (dist-git)', md5_hash)
        else:
            self.log.info("Can't map artifact %s (no hash, ecosystem %s)", name, ecosystem)

        if package_names:
            packages = package_names.split(',')

        return distro, packages

    def _get_downstream_mvn_pkgs(self, eco, pkg):
        packages = []
        self.log.info('Searching for {pkg} in maven repo {repo}...'.
                      format(pkg=pkg, repo=RH_MVN_GA_REPO))
        ga = MavenCoordinates.from_str(pkg).to_repo_url(ga_only=True)
        result = requests.get('{repo}/{pkg}'.format(repo=RH_MVN_GA_REPO, pkg=ga))
        if result.status_code != 200:
            self.log.info('Package {pkg} not found in {repo} (status code {code})'.
                          format(pkg=pkg, repo=RH_MVN_GA_REPO, code=result.status_code))
        else:
            self.log.info('Found {pkg} in {repo}'.format(pkg=pkg, repo=RH_MVN_GA_REPO))
            packages.append(pkg)
        return RH_MVN_DISTRO_NAME, packages

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))

        eco = arguments['ecosystem']
        pkg = arguments['name']
        homepage = self._get_project_homepage(eco, pkg)
        self.log.info('Registering project {e}/{p} to Anitya'.format(e=eco, p=pkg))
        res = self._create_anitya_project(eco, pkg, homepage)
        if res.status_code == 200:
            self.log.info('Project {e}/{p} had already been registered to Anitya'.
                        format(e=eco, p=pkg))
        elif res.status_code == 201:
            self.log.info('Project {e}/{p} was successfully registered to Anitya'.
                        format(e=eco, p=pkg))
        else:
            self.log.error('Failed to create Anitya project {e}/{p}. Anitya response: {r}'.
                         format(e=eco, p=pkg, r=res.text))
            return None
            # TODO: When we move to a proper workflow manager, we'll want to raise TaskError
            #  here instead of just logging an error. Right now we don't want a problem
            #  in AnityaTask to shut down the rest of analysis phases.
            # raise TaskError('Failed to create Anitya project {e}/{p}. Anitya response: {r}'.
            #                 format(e=eco, p=pkg, r=res.text))
        self.log.info('Project {e}/{p} created successfully'.format(e=eco, p=pkg))

        self.log.debug('About to add downstream mapping for %s/%s to Anitya' % (eco, pkg))
        distro_pkgs = {}
        distro_pkgs.update([self._get_downstream_rpm_pkgs(eco, pkg)])
        if self.storage.get_ecosystem(eco).is_backed_by(EcosystemBackend.maven):
            distro_pkgs.update([self._get_downstream_mvn_pkgs(eco, pkg)])
        for distro, package_names in distro_pkgs.items():
            for package_name in package_names:
                res = self._add_downstream_mapping(eco, pkg, distro, package_name)
                if res.status_code == 200:
                    self.log.info('Downstream mapping %s/%s has already been added to project %s' %
                                (distro, package_name, pkg))
                elif res.status_code == 201:
                    self.log.info('Downstream mapping %s/%s was added to project %s' %
                                (distro, package_name, pkg))
                else:
                    raise TaskError('Failed to add downstream mapping %s/%s to project %s' %
                                    (distro, package_name, pkg))

        # we don't want to save any data, so return None
        return None
