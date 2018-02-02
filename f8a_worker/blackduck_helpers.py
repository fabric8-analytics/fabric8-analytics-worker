from requests import get, post
from datetime import timedelta, datetime
from f8a_worker.schemas import (external_schema as schema, SchemaRef)


class BlackDuckException(Exception):
    """Generic exception class thrown by the BlackDuck."""
    pass


class BlackDuckSessionException(BlackDuckException):
    """Thrown when session couldn't be established or has expired."""
    pass


class BlackDuckApiToken(object):
    """API Token Abstraction."""
    def __init__(self, value):
        self._value = value

    @property
    def token(self):
        """Value of this API token."""
        return self._value


class BlackDuckSession(object):
    """
    Session that is valid for certain duration, empiric testing has shown
    that the BlackDuck JSESSION is valid for 24 hours
    """
    def __init__(self, token=None, duration=timedelta(hours=24)):
        self._token = token
        self._duration = duration
        self._created_at = datetime.utcnow()

    @property
    def api_token(self):
        """ Underlying `BlackDuckApiToken` """
        return self._token

    @property
    def duration(self):
        """ Duration of the token expressed as `datetime.timedelta` """
        return self._duration

    def expired(self):
        """ Determine whether the session has expired

        :return: bool, expired or not
        """
        return (self._created_at + self.duration) < datetime.utcnow()


class BlackDuckRelease(object):
    """
    Release object consist of version string, unique identifier
    and `datetime.datetime` information when this particular version was released
    """
    @schema.input(SchemaRef("blackduck-release", "1-0-0"))
    def __init__(self, json_data, project):
        self._version = json_data['version']
        self._id = json_data['versionId']
        self._released_at = datetime.strptime(json_data['releasedOn'], "%Y-%m-%dT%H:%M:%S.%fZ")
        self._project = project

    @property
    def project(self):
        return self._project

    @property
    def version(self):
        """ Release version """
        return self._version

    @property
    def id(self):
        """ Unique identifier """
        return self._id

    @property
    def released_at(self):
        """ Release date time """
        return self._released_at


class BlackDuckProject(object):
    """
    Project contains information about specific {ecosystem}-{package} pair
    """
    @schema.input(SchemaRef("blackduck-project", "1-0-0"))
    def __init__(self, json_data):
        self._source = json_data
        self._name = json_data['name']
        self._id = json_data['id']
        self._canonical_release_id = json_data['canonicalReleaseId']
        self._urls = {k: v for k, v in json_data.items() if k.endswith('Url')}

    @property
    def name(self):
        """ Name of the project """
        return self._name

    @property
    def id(self):
        """ Unique identifier of the project """
        return self._id

    @property
    def urls(self):
        """ Flat list of additional URLs for this project """
        return self._urls

    @property
    def canonical_release_id(self):
        """ Latest release for the given project (in terms of version number) """
        return self._canonical_release_id

    @property
    def source(self):
        """ Source JSON from which this object was parsed """
        return self._source


def needs_session(func):
    """
    Decorator checking that we have a valid session

    :param func: meth, method to decorate
    :return: meth, decorated method
    """
    def wrapper(self, *args, **kwargs):
        if not self._session or self._session.expired():
            raise BlackDuckSessionException("Session token invalid or expired")
        return func(self, *args, **kwargs)
    return wrapper


class BlackDuckHub(object):
    """
    Hub provides access around Black Duck Hub APIs
    """

    # The authentication token is returned in a cookie with this name
    COOKIE_NAME = 'JSESSIONID'

    def __init__(self, url):
        self._url = url
        self._session = None

    @property
    def url(self):
        """ URL of the Hub with trailing slash, example `https://hub.blackducksoftware.com/` """
        return self._url

    def _api(self, param):
        """
        Format a new API call, checks session validity as well

        :param param: str, parameters to append to base url
        :return: str, formatted API call
        """
        return "{}{}".format(self.url, param)

    def _api_get(self, param):
        """
        Perform a get request against the API using local `_session`

        :param param: str, full request URL
        :return: requests.Request, a request object
        """
        return get(self._api(param), cookies={self.COOKIE_NAME: self._session.api_token.token},
                   verify=False)

    def connect_session(self, username, password):
        """
        Establishes a new session with the HUB using the provided credentials

        :param username: str
        :param password: str
        :return: BlackDuckSession, a session object
        :raises: BlackDuckSessionException
        """
        req = post(self._api("j_spring_security_check"),
                   data={
                       'j_username': username,
                       'j_password': password
                   },
                   verify=False)

        if req.status_code != 204:
            raise BlackDuckSessionException("Black Duck authentication error")

        token = req.cookies.get(self.COOKIE_NAME)
        self._session = BlackDuckSession(BlackDuckApiToken(token))

        return self._session

    @needs_session
    def find_project(self, name):
        """
        Find a Project by Name

        :param name: str, name of the project
        :return: BlackDuckProject, found project or `None`
        :raises: BlackDuckSessionException
        """
        preq = self._api_get('api/v1/projects?name=' + name)
        if preq.status_code == 200:
            pdata = preq.json()
            return BlackDuckProject(pdata)
        else:
            return None

    @needs_session
    @schema.result(SchemaRef("blackduck-project-list", "1-0-0"))
    def _list_projects_json(self):
        req = self._api_get('api/projects/')
        if req.status_code == 200:
            return req.json()
        else:
            raise BlackDuckException('Unable to list projects')

    def list_projects(self):
        """
        Lists all projects valid for the current session

        :return: List[BlackDuckProject], list of projects
        :raises: BlackDuckException, BlackDuckSessionException
        """
        names = [project['name'] for project in self._list_projects_json()]
        projects = []

        for name in names:
            projects.append(self.find_project(name))

        return projects

    @needs_session
    def get_releases(self, project_id):
        """
        Get all releases of the given project

        :param project_id: BlackDuckProject or str, project reference or ID
        :return: Dict[str, BlackDuckRelease], a map of version strings to release objects
        :raises: BlackDuckException, BlackDuckSessionException
        """
        if isinstance(project_id, BlackDuckProject):
            project_id = project_id.id

        req = self._api_get('api/v1/projects/{id}/version-summaries'.format(id=project_id))
        if req.status_code == 200:
            data = req.json()
            return {obj['version']: BlackDuckRelease(obj, project_id) for obj in data['items']}
        else:
            raise BlackDuckException('Unable to fetch releases for ' + project_id)

    @needs_session
    @schema.result(SchemaRef("blackduck-vulnerable-bom", "1-0-0"))
    def get_release_bom_json(self, release_id):
        """
        Get the Bill of Materials for specific release

        :param release_id: BlackDuckRelease or str, release reference or ID
        :return: dict, the BOM JSON as a dictionary
        :raises: BlackDuckException, BlackDuckSessionException
        """
        release = release_id

        if isinstance(release_id, BlackDuckRelease):
            release_id = release_id.id

        req = self._api_get('api/projects/{p}/versions/{i}/vulnerable-bom-components'.format(
            i=release_id,
            p=release.project))

        if req.status_code == 200:
            return req.json()
        else:
            raise BlackDuckException('Unable to fetch release information ' + release_id + " " +
                                     release.project)

    @needs_session
    def get_release_code_locations(self, release_id):
        """
        Get code locations for given release

        :param release_id: BlackDuckRelease or str, release reference or ID
        :return: dict, response json containing the retrieved code locations list
        :raises: BlackDuckException, BlackDuckSessionException
        """
        release = release_id

        if isinstance(release_id, BlackDuckRelease):
            release_id = release_id.id

        req = self._api_get('api/projects/{p}/versions/{i}/codelocations'.format(i=release_id,
                                                                                 p=release.project))

        if req.status_code == 200:
            return req.json()
        else:
            raise BlackDuckException('Unable to fetch code locations for {relid} {relproj}'.
                                     format(relid=release_id, relproj=release.project))

    @needs_session
    def get_code_location_scan_summary(self, location_id):
        """
        Get scan summary for given code location ID

        :param location_id: str
        :return: dict, the code location
        :raises: BlackDuckException, BlackDuckSessionException
        """
        req = self._api_get('api/codelocations/{locid}/scan-summaries'.format(locid=location_id))

        if req.status_code == 200:
            return req.json()
        else:
            raise BlackDuckException('Unable to fetch scan summary for code location {locid}'.
                                     format(locid=location_id))
