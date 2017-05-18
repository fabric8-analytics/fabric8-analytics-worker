import os
import logging
from urllib.parse import quote
from f8a_worker.conf import get_configuration, get_postgres_connection_string

_logger = logging.getLogger(__name__)
configuration = get_configuration()


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
