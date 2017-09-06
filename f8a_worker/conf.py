"""
configuration module for f8a

# usage

```
from f8a_worker.conf import get_configuration
configuration = get_configuration()
```

# how it works

It reads configuration from various backends and merges it into a single object (nested dict). You
can check the structure in `f8a_worker.defaultconf`. Configuration is read in following order, where
latter overwrites former (see F8aConfiguration._default_backends):

 1. default configuration read from `f8a_worker.defaultconf`
 2. configuration read from /etc/f8a.yaml
 3. environment variables
 4. dict passed to `get_configuration` which is able to override everything

This nested dict is referred in comments as merged configuration.


# accessing configuration

Values can be retrieved via `configuration.value` where value is the name specified as
key in `add_configuration_entry`; you may also define convenience aliases for these dynamic lookups,
check bottom of F8aConfiguration

"""

import os
import re
import json
import logging
from copy import deepcopy
from urllib.parse import quote

from f8a_worker import defaultconf

import anymarkup


# singleton so we don't access backends multiple times
configuration = None
logger = logging.getLogger("f8a_worker")


def merge_dicts(a, b):
    """
    merge dict `b` into dict `a`, everything from `a` is overriden by `b`

    taken from http://stackoverflow.com/a/7205107/909579
    """
    for key in b:
        if key in a:
            # so what if a is not a dict and b is?
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key])
            else:
                # override
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a


class ConfigurationException(Exception):
    pass


class ConfigurationEntry(object):
    def __init__(self, key, path, graceful, env_var_name=None):
        """
        definition of one entry in configuration

        :param key: str, ID + key to access the value via getattr
        :param path: list of str, path to value within merged configuration
        :param graceful: bool, fail if not present?
        :param env_var_name: name of environment variable, used in EnvVarBackend
        """
        self.key = key
        self.path = path
        self.graceful = graceful
        self.env_var_name = env_var_name


class Configuration(object):
    def __init__(self, backends):
        """
        :param backends: list of ConfigurationBackend instances
        """
        self.backends = backends
        self.entries = {}
        self._data = None

    @property
    def data(self):
        """
        this is lazy evaluator; so we don't have to call some method in F8aConfiguration
        """
        if self._data is None:
            self._data = {}
            for b in self.backends:
                merge_dicts(self._data, b.load(self.entries.values()))

            # this log may be valuable during debugging even though it will likely be pretty long
            logger.debug(json.dumps(self.data, indent=2))
        return self._data

    def __getattr__(self, item):
        """
        by default, do what getattr this; in case it fails, look for the configuration
        value in self.entries
        """
        try:
            # original behavior
            return self.__dict__[item]
        except KeyError:
            logger.debug(self.__dict__)
            try:
                c = self.__dict__["entries"][item]
            except KeyError as exc:
                raise AttributeError("there is no configuration key %r" % item) from exc
            else:
                return self.get(c.path, graceful=c.graceful)

    def add_configuration_entry(self, key, path, graceful=True, env_var_name=None):
        """
        definition of one entry in configuration

        :param key: str, ID + key to access the value via getattr
        :param path: list of str, path to value within merged configuration
        :param graceful: bool, fail if not present?
        :param env_var_name: name of environment variable, used in EnvVarBackend
        """
        self.entries[key] = ConfigurationEntry(key, path, graceful, env_var_name=env_var_name)

    def get(self, path, graceful=True):
        """
        get value from merged configuration

        :param path: list of str, path within configuration
        :param graceful: bool, fail if the value doesn't exist?
        :return: value it found or None
        """
        node = self.data
        for p in path:
            try:
                node = node[p]
            except (KeyError, ValueError) as ex:
                logger.info("got exc %r when getting value %s", ex, p)
                if graceful:
                    return
                else:
                    raise ConfigurationException("Can't get value %s from %s" % (p, node)) from ex
        return node


class ConfigurationBackend(object):
    """
    API for classes which are responsible to return object with configuration from arbitrary sources
    e.g. file, env var, python object, database, URL, written on a paper...
    """
    def __init__(self):
        pass

    def load(self, entries_list):
        """
        load configuration from specific backend

        :param entries_list: list of ConfigurationEntry instances
        :return: dict, used to merge
        """
        return {}


class FileBackend(ConfigurationBackend):
    """
    obtain configuration from a file
    """

    def __init__(self, path, graceful=False):
        """
        :param path: str, path to file
        :param graceful: bool, fail when file can't be accessed
        """
        super(FileBackend, self).__init__()
        self.path = path
        self.graceful = graceful

    def load(self, entries_list):
        try:
            return anymarkup.parse_file(self.path)
        except (anymarkup.AnyMarkupError, OSError, IOError) as ex:
            logger.debug("can't access file %s: %r", self.path, ex)
            if self.graceful:
                return {}
            else:
                raise ConfigurationException("Can't open file %s" % self.path) from ex


class ObjectBackend(ConfigurationBackend):
    """
    obtain configuration from a python object (nested dict)
    """

    def __init__(self, obj):
        super(ObjectBackend, self).__init__()
        self.obj = deepcopy(obj)  # just in case, copy it

    def load(self, entries_list):
        return self.obj


class EnvVarBackend(ObjectBackend):
    """
    obtain configuration from environment variables
    """

    def __init__(self):
        super(EnvVarBackend, self).__init__(os.environ)

    def load(self, entries_list):
        result = {}
        for entry in entries_list:
            if entry.env_var_name is not None:
                self._translate_item(result, entry.env_var_name, entry.path)
        return result

    def _translate_item(self, result_dict, key_name, path):
        """
        util function: translate value from env var to generic configuration format

        :param result_dict: dict used for merge
        :param key_name: env var name
        :param path: path to variable in merged configuration
        :return: None
        """
        if len(path) <= 0:
            raise ValueError("path needs to have at least one item")
        val = self.obj.get(key_name, None)
        if val:
            d = result_dict
            for p in path[:-1]:
                # we could have a custom dict class here, not sure if it's worth it
                d.setdefault(p, {})
                d = d[p]
            d[path[-1]] = val


def get_postgres_connection_string(url_encoded_password=True):
    f8a_postgres = os.environ.get('F8A_POSTGRES')
    if f8a_postgres:
        if url_encoded_password:
            f8a_postgres = re.sub(r'(postgresql://.+:)([^@]+)(@.+)',
                                  lambda x: '{}{}{}'.format(x.group(1), quote(x.group(2), safe=''), x.group(3)),
                                  f8a_postgres,
                                  count=1)
        return f8a_postgres

    password = os.environ.get('POSTGRESQL_PASSWORD', '')
    postgres_env = {'POSTGRESQL_USER': os.environ.get('POSTGRESQL_USER'),
                    'POSTGRESQL_PASSWORD': quote(password, safe='') if url_encoded_password else password,
                    'PGBOUNCER_SERVICE_HOST': os.environ.get('PGBOUNCER_SERVICE_HOST'),
                    'POSTGRESQL_DATABASE': os.environ.get('POSTGRESQL_DATABASE')}
    return 'postgresql://{POSTGRESQL_USER}:{POSTGRESQL_PASSWORD}@' \
           '{PGBOUNCER_SERVICE_HOST}:5432/{POSTGRESQL_DATABASE}?' \
           'sslmode=disable'.format(**postgres_env)


class F8aConfiguration(Configuration):
    """
    f8a-specific configuration
    """

    def __init__(self, backends=None, configuration_override=None):
        """
        :param backends: list of ConfigurationBackend instances, if not supplied,
                         self._default_backends are used
        :param configuration_override: dict, overrides configuration of all backends, has only
                                       effect when using default backends
        """
        if backends is None:
            self.backends = self._default_backends(configuration_override=configuration_override)
        else:
            self.backends = backends

        super(F8aConfiguration, self).__init__(self.backends)

        self.add_configuration_entry(
            "postgres_connection", ["postgres", "connection_string"], env_var_name="F8A_POSTGRES")
        self.add_configuration_entry(
            "worker_data_dir", ["worker", "data_dir"], env_var_name="WORKER_DATA_DIR")
        self.add_configuration_entry(
            "github_token", ["github", "token"], env_var_name="GITHUB_TOKEN")
        self.add_configuration_entry("npmjs_changes_url", ["npmjs_changes_url"])
        self.add_configuration_entry("coreapi_server_url", ["coreapi_server", "url"])
        self.add_configuration_entry("git_user_name", ["git", "user_name"])
        self.add_configuration_entry("git_user_email", ["git", "user_email"])
        self.add_configuration_entry(
            "broker_connection", ["broker", "connection_string"], env_var_name="F8A_CELERY_BROKER")
        self.add_configuration_entry("anitya_url", ["anitya", "url"], env_var_name="F8A_ANITYA")

        self.add_configuration_entry(
            "blackduck_host", ["blackduck", "host"], env_var_name="BLACKDUCK_HOST"
        )
        self.add_configuration_entry(
            "blackduck_scheme", ["blackduck", "scheme"], env_var_name="BLACKDUCK_SCHEME"
        )
        self.add_configuration_entry(
            "blackduck_port", ["blackduck", "port"], env_var_name="BLACKDUCK_PORT"
        )
        self.add_configuration_entry(
            "blackduck_username", ["blackduck", "username"], env_var_name="BLACKDUCK_USERNAME"
        )
        self.add_configuration_entry(
            "blackduck_password", ["blackduck", "password"], env_var_name="BLACKDUCK_PASSWORD"
        )
        self.add_configuration_entry(
            "blackduck_path", ["blackduck", "path"], env_var_name="BLACKDUCK_PATH"
        )
        self.add_configuration_entry(
            "bigquery_json_key", ["bigquery", "json_key"], env_var_name="BIGQUERY_JSON_KEY"
        )
        self.add_configuration_entry(
            "pulp_url", ["pulp", "url"], env_var_name="PULP_URL"
        )
        self.add_configuration_entry(
            "pulp_username", ["pulp", "username"], env_var_name="PULP_USERNAME"
        )
        self.add_configuration_entry(
            "pulp_password", ["pulp", "password"], env_var_name="PULP_PASSWORD"
        )

    @staticmethod
    def _default_backends(configuration_override=None):
        """
        get configuration from default sources

        :param configuration_override: dict, overrides configuration of all backends
        :return: list of ConfigurationBackend instances
        """
        config_path = os.getenv("F8A_CONFIG_PATH", "/etc/f8a.yaml")
        secrets_path = os.getenv("F8A_SECRETS_PATH", "/var/lib/secrets/secrets.yaml")
        return [
            ObjectBackend(defaultconf.data),
            FileBackend(path=config_path, graceful=True),
            FileBackend(path=secrets_path, graceful=True),
            EnvVarBackend(),
            ObjectBackend(configuration_override or {}),
        ]

    # these are basically convenience aliases just for sake how to create those

    def get_coreapi_server_url(self):
        return self.coreapi_server_url


def get_configuration(configuration_override=None):
    """
    :param configuration_override: dict, overrides configuration of all backends; if set,
                                   configuration is reinitialized
    :return: instance of F8aConfiguration
    """
    global configuration
    if configuration_override is not None or configuration is None:
        configuration = F8aConfiguration(configuration_override=configuration_override)
        logger.debug("creating new instance of F8aConfiguration: %s", id(configuration))
    return configuration


def is_local_deployment():
    """
    :return: True if we are running locally
    """

    return os.environ.get('F8A_UNCLOUDED_MODE', '0').lower() in ('1', 'true', 'yes')
