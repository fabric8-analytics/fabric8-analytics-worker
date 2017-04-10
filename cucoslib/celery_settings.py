import os
import json
import logging
from urllib.parse import quote
from celery.signals import setup_logging
from logstash.formatter import LogstashFormatterVersion1
from cucoslib.conf import get_configuration, get_postgres_connection_string, is_local_deployment

_logger = logging.getLogger(__name__)
configuration = get_configuration()


class _StringLogstashFormatterV1(LogstashFormatterVersion1):
    """ Logstash formatter to string, Version1 """
    def format(self, record):
        # The default formatter should be used with LogstashHandler that accepts bytes, let's decode the message that is
        # a JSON and print it to stdout as logs are gathered transparently
        return super().format(record).decode()


class _SelinonLocalTraceFormatter(LogstashFormatterVersion1):
    """ Format Selinon traces for local development"""
    def format(self, record):
        # Derivation from LogstashFormatterVersion1 is because of reusing keys gathering from
        # log call - see get_extra_fields()
        #
        # This formatter is used for local development so there is no need to set up two different
        # loggers (we need to support 'extra' kwarg passed to logger because of python-logstash API design)
        message = {
            '@fields': self.get_extra_fields(record),
            '@message': record.getMessage(),
            'logger_name': record.name,
            'level': record.levelname
        }

        return json.dumps(message, sort_keys=True)


def _use_sqs():
    """
    :return: True if worker should use Amazon SQS
    """
    key_id = len(os.environ.get('AWS_SQS_ACCESS_KEY_ID', '')) > 0
    access_key = len(os.environ.get('AWS_SQS_SECRET_ACCESS_KEY', '')) > 0

    res = int(key_id) + int(access_key)

    if res == 1:
        raise RuntimeError("In order to use AWS SQS you have to provide both 'AWS_SQS_ACCESS_KEY_ID' and "
                           "'AWS_SQS_SECRET_ACCESS_KEY' environment variables")

    # Make sure we do not pass these env variables - according to Celery docs they can be used only with 'sqs://'
    if "AWS_ACCESS_KEY_ID" in os.environ:
        raise RuntimeError("Do not use AWS_ACCESS_KEY_ID in order to access SQS, use 'AWS_SQS_ACCESS_KEY_ID'")

    if "AWS_SECRET_ACCESS_KEY" in os.environ:
        raise RuntimeError("Do not use AWS_SECRET_ACCESS_KEY in order to access SQS, use 'AWS_SQS_SECRET_ACCESS_KEY'")

    return res != 0


class CelerySettings(object):
    _DEFAULT_SQS_REGION = 'us-east-1'
    _DEFAULT_RESULT_BACKEND = 'db+' + get_postgres_connection_string()

    # Generic worker options
    timezone = 'UTC'
    task_acks_late = True
    result_backend = os.environ.get('CELERY_RESULT_BACKEND') or _DEFAULT_RESULT_BACKEND

    # do not retry on connection errors, rather let OpenShift kill the worker
    broker_connection_retry = False

    # Set up message broker
    if _use_sqs():
        broker_url = 'sqs://{aws_access_key_id}:{aws_secret_access_key}@'.format(
            aws_access_key_id=quote(os.environ['AWS_SQS_ACCESS_KEY_ID'], safe=''),
            aws_secret_access_key=quote(os.environ['AWS_SQS_SECRET_ACCESS_KEY'], safe=''),
        )
        broker_transport_options = {
            # number of seconds to wait for the worker to acknowledge the task before the message is
            # redelivered to another worker
            'visibility_timeout': 1800,
            # number of seconds for polling, the more frequent we poll, the more money we pay
            'polling_interval': 2,
            # 'queue_name_prefix': 'bayesian-',
            # see amazon_endpoints.js based on http://docs.aws.amazon.com/general/latest/gr/rande.html#sqs_region
            'region': os.environ.get('AWS_SQS_REGION', _DEFAULT_SQS_REGION)
        }

        _logger.debug('AWS broker transport options: %s', broker_transport_options)
    else:
        # Fallback to default Broker configuration (e.g. RabbitMQ)
        broker_url = configuration.broker_connection
        task_serializer = 'json'
        result_serializer = 'json'
        accept_content = ['json']

    def __init__(self):
        raise NotImplementedError("Unable to instantiate")

    @classmethod
    def disable_result_backend(cls):
        """Disable backend so we don't need to connect to it if not necessary"""
        cls.result_backend = None


@setup_logging.connect
def configure_logging(**kwargs):
    """ Set up logging for worker """
    is_local = is_local_deployment()
    formatter = 'local' if is_local else 'deployment'
    selinon_formatter = 'selinon_local' if is_local else 'deployment'

    logging_formatters = {
        'local': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'deployment': {
            '()': _StringLogstashFormatterV1
        },
        'selinon_local': {
            '()': _SelinonLocalTraceFormatter
        }
    }

    handlers = {
        'default': {
            'level': 'INFO',
            'formatter': formatter,
            'class': 'logging.StreamHandler',
        },
        'selinon_trace': {
            'level': 'DEBUG',
            'formatter': selinon_formatter,
            'class': 'logging.StreamHandler',
        },
        'verbose': {
            'level': 'DEBUG',
            'formatter': formatter,
            'class': 'logging.StreamHandler',
        },
    }

    # If you would like to track some library, place it's handler here with appropriate entry - see celery as an example
    loggers = {
        '': {
            'handlers': ['default'],
            'level': 'INFO',
        },
        'selinon': {
            'handlers': ['verbose'],
            'level': 'DEBUG',
            'propagate': False
        },
        'selinonlib': {
            'handlers': ['verbose'],
            'level': 'DEBUG',
            'propagate': False
        },
        'cucoslib.dispatcher.trace': {
            'handlers': ['selinon_trace'],
            'level': 'DEBUG',
            'propagate': False
        },
        'cucoslib': {
            'handlers': ['verbose'],
            'level': 'DEBUG',
            'propagate': False
        },
        'kombu': {
            'handlers': ['verbose'],
            'level': 'DEBUG',
            'propagate': False
        },
        'celery': {
            'handlers': ['verbose'],
            'level': 'DEBUG',
            'propagate': False
        }
    }

    logging.config.dictConfig({
        'version': 1,
        'loggers': loggers,
        'formatters': logging_formatters,
        'handlers': handlers
    })

