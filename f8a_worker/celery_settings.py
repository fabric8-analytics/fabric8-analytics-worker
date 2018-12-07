"""Setup Celery."""

import os
import logging
from urllib.parse import quote
from celery.signals import setup_logging
from f8a_worker.defaults import configuration

_logger = logging.getLogger(__name__)


def _use_sqs():
    """Check if worker should use Amazon SQS.

    :return: True if worker should use Amazon SQS
    """
    has_key_id = configuration.AWS_SQS_ACCESS_KEY_ID is not None
    has_access_key = configuration.AWS_SQS_SECRET_ACCESS_KEY is not None

    if has_key_id != has_access_key:
        raise RuntimeError("In order to use AWS SQS you have to provide both "
                           "'AWS_SQS_ACCESS_KEY_ID' and "
                           "'AWS_SQS_SECRET_ACCESS_KEY' environment variables")

    # Make sure we do not pass these env variables - according to Celery docs
    # they can be used only with 'sqs://'
    if "AWS_ACCESS_KEY_ID" in os.environ:
        raise RuntimeError("Do not use AWS_ACCESS_KEY_ID in order to access SQS, "
                           "use 'AWS_SQS_ACCESS_KEY_ID'")

    if "AWS_SECRET_ACCESS_KEY" in os.environ:
        raise RuntimeError("Do not use AWS_SECRET_ACCESS_KEY in order to access SQS, "
                           "use 'AWS_SQS_SECRET_ACCESS_KEY'")

    return has_key_id and has_access_key


class CelerySettings(object):
    """Setup Celery."""

    _DEFAULT_SQS_REGION = 'us-east-1'
    _DEFAULT_RESULT_BACKEND = 'db+' + configuration.POSTGRES_CONNECTION

    # Generic worker options
    timezone = 'UTC'
    task_acks_late = True
    result_backend = configuration.CELERY_RESULT_BACKEND or _DEFAULT_RESULT_BACKEND

    # do not retry on connection errors, rather let OpenShift kill the worker
    broker_connection_retry = False

    # Set up message broker
    if _use_sqs():
        broker_url = 'sqs://{aws_access_key_id}:{aws_secret_access_key}@'.format(
            aws_access_key_id=quote(configuration.AWS_SQS_ACCESS_KEY_ID, safe=''),
            aws_secret_access_key=quote(configuration.AWS_SQS_SECRET_ACCESS_KEY, safe=''),
        )
        broker_transport_options = {
            # number of seconds to wait for the worker to acknowledge the task before the message is
            # redelivered to another worker
            'visibility_timeout': 1800,
            # number of seconds for polling, the more frequent we poll, the more money we pay
            'polling_interval': 2,
            # 'queue_name_prefix': 'bayesian-',
            # see amazon_endpoints.js based on
            # http://docs.aws.amazon.com/general/latest/gr/rande.html#sqs_region
            'region': configuration.AWS_SQS_REGION or _DEFAULT_SQS_REGION
        }

        _logger.debug('AWS broker transport options: %s', broker_transport_options)
    else:
        # Fallback to default Broker configuration (e.g. RabbitMQ)
        broker_url = configuration.BROKER_CONNECTION
        task_serializer = 'json'
        result_serializer = 'json'
        accept_content = ['json']

    def __init__(self):
        """Not implemented."""
        raise NotImplementedError("Unable to instantiate")

    @classmethod
    def disable_result_backend(cls):
        """Disable backend so we don't need to connect to it if not necessary."""
        cls.result_backend = None


@setup_logging.connect
def configure_logging(**kwargs):
    """Set up logging for worker."""
    level = 'DEBUG' if configuration.is_local_deployment() else 'INFO'

    handlers = {
        'default': {
            'level': 'INFO',
            'formatter': 'default',
            'class': 'logging.StreamHandler',
        },
        'selinon_trace': {
            'level': level,
            'formatter': 'selinon_trace_formatter',
            'class': 'logging.StreamHandler',
        },
        'verbose': {
            'level': level,
            'formatter': 'default',
            'class': 'logging.StreamHandler',
        },
    }

    # If you would like to track some library, place it's handler here with
    # appropriate entry - see celery as an example
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
        'f8a_worker.dispatcher.trace': {
            'handlers': ['selinon_trace'],
            'level': 'DEBUG',
            'propagate': False
        },
        'f8a_worker': {
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
        'formatters': {
            'default': {
              'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
            'selinon_trace_formatter': {
                # no prefixes to parse JSON when aggregating
                'format': '%(message)s'
            }
        },
        'handlers': handlers
    })
