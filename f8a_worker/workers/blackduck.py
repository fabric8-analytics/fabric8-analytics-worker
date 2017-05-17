from f8a_worker.utils import TimedCommand
from f8a_worker.schemas import SchemaRef
from f8a_worker.base import BaseTask
from f8a_worker.conf import get_configuration
from f8a_worker.blackduck_helpers import BlackDuckHub
from f8a_worker.object_cache import ObjectCache
from f8a_worker.errors import TaskError
from os import listdir, path

config = get_configuration()

class BlackDuckDataNotReady(Exception):
    def __init__(self, project, version):
        self.project = project
        self.version = version

    def __str__(self):
        return 'BlackDuck data not ready yet for {p} {v}'.format(p=self.project, v=self.version)


class BlackDuckTask(BaseTask):
    _analysis_name = 'blackduck'
    description = 'Scan the package using Black Duck'
    _valid_ecosystems = ["npm", "maven", "pypi"]
    _allow_cli_scan = True
    schema_ref = SchemaRef(_analysis_name, '1-0-0')

    _BLACKDUCK_CLI_TIMEOUT = 600

    def _format_hub_url(self):
        """
        Format Hub connection string from supplied config

        :return:
        """
        return "{scheme}://{host}:{port}/".format(scheme=config.blackduck_scheme,
                                                  host=config.blackduck_host,
                                                  port=config.blackduck_port)

    def _is_valid_ecosystem(self, ecosystem_id):
        """
        Determine whether the given ecosystem is valid for
        Black Duck analysis

        :param ecosystem_id: int, the ID of the ecosystem
        :return: bool
        """
        return ecosystem_id in self._valid_ecosystems

    def _find_blackduck_cli_root(self):
        """
        Find the base directory where the BlackDuck CLI got
        extracted

        :return: str, path to the CLI root
        """
        base = config.blackduck_path
        dirs = listdir(base)
        if not dirs:
            raise TaskError("Unable to find BlackDuck CLI directory")
        if len(dirs) > 1:
            raise TaskError("More than 1 BlackDuck CLI directory")

        return path.join(base, dirs.pop())

    def _prepare_command(self, project, version, archive):
        """
        Prepare the necessary CLI parameters

        :param project: str, name of the project
        :param version: str, version of the release
        :param archive: str, path to the archive with the sources
        :return: List[str], command list ready to be run
        """

        binary = "{base}/{rel}".format(base=self._find_blackduck_cli_root(),
                                       rel="bin/scan.cli.sh")

        return [binary,
                "--host", config.blackduck_host,
                "--port", str(int(config.blackduck_port)),
                "--scheme", config.blackduck_scheme,
                "--username", config.blackduck_username,
                "--project", project,
                "--release", version,
                archive]

    def _get_release(self, hub, project, version):
        """
        Get release ID for given project version

        :param hub: BlackDuckHub, hub object to use
        :param project: str, name of the project
        :param version: str, version
        :return: BlackDuckRelease object or None if not found
        """
        # check that the specified project exists
        proj = hub.find_project(project)
        if not proj:
            return None

        # check that we have the proper version
        releases = hub.get_releases(proj)
        return releases.get(version, None)

    def _release_data(self, hub, project, version):
        """
        Fetch release data for the given project and version

        :param hub: BlackDuckHub, hub object to use
        :param project: str, name of the project
        :param version: str, version
        :return: dict, BoM information about the release
        """
        release = self._get_release(hub, project, version)
        if release is None:
            return None
        return hub.get_release_bom_json(release)

    def _get_hub(self):
        # connect to the Black Duck Hub
        hub_url = self._format_hub_url()
        self.log.debug("hub url: {url}".format(url=hub_url))
        hub = BlackDuckHub(hub_url)
        hub.connect_session(config.blackduck_username, config.blackduck_password)
        return hub

    def _get_project_name(self, arguments):
        return "{ecosystem}-{package}".format(ecosystem=arguments['ecosystem'],
                                              package=arguments['name'])

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        result_data = {'status': 'unknown',
                       'summary': [],
                       'details': {}}

        if self._is_valid_ecosystem(arguments['ecosystem']):
            hub = self._get_hub()

            # BlackDuck project doesn't have a notion of ecosystem, so we need to
            # namespace the project names ourselves, so for package `crumb` in the NPM ecosystem
            # we'll end up with the name `npm-crumb`
            project = self._get_project_name(arguments)
            version = arguments['version']

            # Check if the given project had already been scanned
            data = self._release_data(hub, project, version)

            if not data and self._allow_cli_scan:
                self.log.debug("No data available for project {p} {v}".format(p=project, v=version))
                # No data available, issue a new scan and re-query release data
                source_tarball_path = ObjectCache.get_from_dict(arguments).get_source_tarball()
                command = self._prepare_command(project, version, source_tarball_path)
                self.log.debug("Executing command, timeout={timeout}: {cmd}".format(timeout=self._BLACKDUCK_CLI_TIMEOUT,
                                                                                    cmd=command))
                bd = TimedCommand(command)
                status, output, error = bd.run(timeout=self._BLACKDUCK_CLI_TIMEOUT,
                                               update_env={'BD_HUB_PASSWORD': config.blackduck_password})
                self.log.debug("status = %s, error = %s", status, error)
                self.log.debug("output = %s", output)
                data = self._release_data(hub, project, version)

            self.log.debug("Release data for project {p} {v}: {d}".format(p=project, v=version, d=data))
            result_data['details'] = data
            result_data['status'] = 'success' if data else 'error'
        else:
            result_data['status'] = 'error'

        return result_data


class BlackDuckLatentCollector(BlackDuckTask):
    _allow_cli_scan = False

    def _data_ready(self, hub, project, version):
        release = self._get_release(hub, project, version)
        if release is None:
            return False
        code_locations = hub.get_release_code_locations(release)
        for loc in code_locations['items']:
            locid = loc['_meta']['href'].strip('/').split('/')[-1]
            scan_sums = hub.get_code_location_scan_summary(locid)
            for ssum in scan_sums['items']:
                if ssum['status'] != 'COMPLETE':
                    return False
        return True

    def execute(self, arguments):
        hub = self._get_hub()

        self.log.info('Determining if data is already available at BD Hub ...')
        if not self._data_ready(hub, self._get_project_name(arguments), arguments['version']):
            self.log.info('Data not available yet at BD Hub, retrying ...')
            raise BlackDuckDataNotReady(self._get_project_name(arguments), arguments['version'])
        self.log.info('Data is available at BD Hub, extracting ...')

        data = super().execute(arguments)
        if not data['details']:
            raise TaskError("No data from Hub")

        return data
