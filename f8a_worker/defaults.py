#!/usr/bin/env python3
from os import environ
from urllib.parse import quote


class F8AConfiguration(object):
    def _make_postgres_string(password):
        """
        Method creates postgres connection string. It's parametrized, so it's possible to
        create either quoted or unquoted version of connection string.
        Note that it's outside of class since there is no simple way how to call it inside the class
        without class initialization.
        :param password: password which will be embedded into Postgres connection string
        :return: fully working postgres connection string
        """
        connection = 'postgresql://{user}:{password}@{pgbouncer_host}:{pgbouncer_port}' \
                     '/{database}?sslmode=disable'. \
            format(user=environ.get('POSTGRESQL_USER'),
                   password=password,
                   pgbouncer_host=environ.get('PGBOUNCER_SERVICE_HOST', 'coreapi-pgbouncer'),
                   pgbouncer_port=environ.get('PGBOUNCER_SERVICE_PORT', '5432'),
                   database=environ.get('POSTGRESQL_DATABASE'))
        return connection

    BIGQUERY_JSON_KEY = environ.get('GITHUB_CONSUMER_KEY', 'not-set')

    # Pulp configuration
    PULP_URL = environ.get('PULP_URL', 'not-set')
    PULP_USERNAME = environ.get('PULP_USERNAME', 'not-set')
    PULP_PASSWORD = environ.get('PULP_PASSWORD', 'not-set')

    # BlackDuck configuration
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

    UNQUOTED_POSTGRES_CONNECTION = _make_postgres_string(environ.get('POSTGRESQL_PASSWORD', ''))
    POSTGRES_CONNECTION = _make_postgres_string(
        quote(environ.get('POSTGRESQL_PASSWORD', ''), safe=''))

    WORKER_DATA_DIR = environ.get('WORKER_DATA_DIR', 'not-set')

    # Scancode configuration
    SCANCODE_LICENSE_SCORE = environ.get('SCANCODE_LICENSE_SCORE', '20')  # scancode's default is 0
    SCANCODE_TIMEOUT = environ.get('SCANCODE_TIMEOUT', '120')  # scancode's default is 120
    SCANCODE_PROCESSES = environ.get('SCANCODE_PROCESSES', '1')  # scancode's default is 1
    SCANCODE_PATH = environ.get('SCANCODE_PATH', '/opt/scancode-toolkit/')
    SCANCODE_IGNORE = ['*.pyc', '*.so', '*.dll', '*.rar', '*.jar',
                       '*.zip', '*.tar', '*.tar.gz', '*.tar.xz']  # don't scan binaries

    # AWS S3
    AWS_S3_REGION = environ.get('AWS_S3_REGION')
    AWS_S3_ACCESS_KEY_ID = environ.get('AWS_S3_ACCESS_KEY_ID')
    AWS_S3_SECRET_ACCESS_KEY = environ.get('AWS_S3_SECRET_ACCESS_KEY')

    S3_ENDPOINT_URL = environ.get('S3_ENDPOINT_URL')
    DEPLOYMENT_PREFIX = environ.get('DEPLOYMENT_PREFIX')
    BAYESIAN_SYNC_S3 = int(environ.get('BAYESIAN_SYNC_S3', 0)) == 1

    # AWS SQS
    AWS_SQS_ACCESS_KEY_ID = environ.get('AWS_SQS_ACCESS_KEY_ID')
    AWS_SQS_SECRET_ACCESS_KEY = environ.get('AWS_SQS_SECRET_ACCESS_KEY')
    CELERY_RESULT_BACKEND = environ.get('CELERY_RESULT_BACKEND')
    AWS_SQS_REGION = environ.get('AWS_SQS_REGION')

    # TODO: Add default value for JAVANCSS_PATH and OWASP_DEP_CHECK_PATH
    JAVANCSS_PATH = environ.get('JAVANCSS_PATH')
    OWASP_DEP_CHECK_PATH = environ.get('OWASP_DEP_CHECK_PATH')

    # Graph stuff
    try:
        USAGE_THRESHOLD = int(environ.get("LOW_USAGE_THRESHOLD", "5000"))
    except (TypeError, ValueError):
        # low usage threshold is set to default 5000 as the env variable value is non numeric
        USAGE_THRESHOLD = 5000

    try:
        POPULARITY_THRESHOLD = int(environ.get("LOW_POPULARITY_THRESHOLD", "5000"))
    except (TypeError, ValueError):
        # low usage threshold is set to default 5000 as the env variable value is non numeric
        POPULARITY_THRESHOLD = 5000

    BAYESIAN_GREMLIN_HTTP_SERVICE_HOST = environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST",
                                                     "localhost")
    BAYESIAN_GREMLIN_HTTP_SERVICE_PORT = environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182")

    @classmethod
    def is_local_deployment(cls):
        """
        :return: True if we are running locally
        """
        return environ.get('F8A_UNCLOUDED_MODE', '0').lower() in ('1', 'true', 'yes')


configuration = F8AConfiguration()
