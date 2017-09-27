#!/usr/bin/env python3
from os import environ
from urllib.parse import quote


class F8AConfiguration(object):
    BIGQUERY_JSON_KEY = environ.get('GITHUB_CONSUMER_KEY', 'not-set')

    PULP_URL = environ.get('PULP_URL', 'not-set')
    PULP_USERNAME = environ.get('PULP_USERNAME', 'not-set')
    PULP_PASSWORD = environ.get('PULP_PASSWORD', 'not-set')

    BLACKDUCK_HOST = environ.get('BLACKDUCK_HOST', 'not-set')
    BLACKDUCK_SCHEME = environ.get('BLACKDUCK_SCHEME', 'not-set')
    BLACKDUCK_PORT = environ.get('BLACKDUCK_PORT', 'not-set')
    BLACKDUCK_USERNAME = environ.get('BLACKDUCK_USERNAME', 'not-set')
    BLACKDUCK_PASSWORD = environ.get('BLACKDUCK_PASSWORD', 'not-set')
    BLACKDUCK_PATH = environ.get('BLACKDUCK_PATH', 'not-set')

    ANITYA_URL = "http://{host}:{port}".format(host=environ.get('ANITYA_HOST', 'anitya-server'),
                                               port=environ.get('ANITYA_PORT', '5000'))

    BROKER_CONNECTION = "amqp://guest@{host}:{port}".format(
        host=environ.get('RABBITMQ_SERVICE_SERVICE_HOST', 'coreapi-broker'),
        port=environ.get('RABBITMQ_SERVICE_SERVICE_PORT', '5672'))

    GIT_USER_NAME = environ.get('GIT_USER_NAME', 'f8a')
    GIT_USER_EMAIL = environ.get('GIT_USER_EMAIL', 'f8a@f8a')

    GITHUB_TOKEN = environ.get('GITHUB_TOKEN', 'not-set')

    # URL to npmjs couch DB, which returns stream of changes happening in npm registry
    NPMJS_CHANGES_URL = environ.get('NPMJS_CHANGES_URL',
                                    "https://skimdb.npmjs.com/registry/"
                                    "_changes?descending=true&include_docs=true&feed=continuous")

    POSTGRES_CONNECTION = 'postgresql://{user}:{password}@{pgbouncer_host}:{pgbouncer_port}' \
                          '/{database}?sslmode=disable'. \
        format(user=environ.get('POSTGRESQL_USER'),
               password=quote(environ.get('POSTGRESQL_PASSWORD', ''), safe=''),
               pgbouncer_host=environ.get('PGBOUNCER_SERVICE_HOST', 'coreapi-pgbouncer'),
               pgbouncer_port=environ.get('PGBOUNCER_SERVICE_PORT', '5432'),
               database=environ.get('POSTGRESQL_DATABASE'))

    WORKER_DATA_DIR = environ.get('WORKER_DATA_DIR', 'not-set')

    @classmethod
    def is_local_deployment(cls):
        """
        :return: True if we are running locally
        """
        return environ.get('F8A_UNCLOUDED_MODE', '0').lower() in ('1', 'true', 'yes')
