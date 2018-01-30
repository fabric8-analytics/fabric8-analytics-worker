#!/usr/bin/env python3
"""Set up queue attributes before worker start up so we are sure all queues are properly set up."""

import boto3
import os
import logging
import sys
from time import sleep
from datetime import timedelta

logging.basicConfig(level=logging.WARNING)
_logger = logging.getLogger(__name__)
# Make verbose only logger in this script, botocore tends to be super
# verbose when performing requests
_logger.setLevel(logging.DEBUG)


_AWS_SQS_REGION = os.getenv('AWS_SQS_REGION', 'us-east-1')
_AWS_ACCESS_KEY_ID = os.getenv('AWS_SQS_ACCESS_KEY_ID')
_AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SQS_SECRET_ACCESS_KEY')
_DEPLOYMENT_PREFIX = os.getenv('DEPLOYMENT_PREFIX')


def set_queue_attributes(queue_names):
    """Set required queue attributes for all queues used by worker.

    :param queue_names: a list of queue names to set attribute to
    :type queue_names: list
    """
    client = boto3.client(
        'sqs',
        aws_access_key_id=_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=_AWS_SECRET_ACCESS_KEY,
        region_name=_AWS_SQS_REGION
    )

    for queue_name in queue_names:
        _logger.info("Creating or requesting QueueURL for queue '{}'".format(queue_name))
        if queue_name.endswith('.fifo'):
            response = client.create_queue(QueueName=queue_name, Attributes={'FifoQueue': 'true'})
        else:
            response = client.create_queue(QueueName=queue_name)

        queue_url = response.get('QueueUrl')
        if not queue_url:
            raise RuntimeError("Response from remote does not contain QueueUrl, "
                               "cannot adjust queue attributes, response: {}".format(response))

        response = client.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                'MessageRetentionPeriod': str(int(timedelta(days=14).total_seconds()))
            }
        )
        _logger.debug("Remote responded with %r after setting queue attributes for %r",
                      response, queue_name)

        if _DEPLOYMENT_PREFIX:
            response = client.tag_queue(
                QueueUrl=queue_url,
                Tags={
                    'ENV': _DEPLOYMENT_PREFIX
                }
            )
            _logger.debug("Remote responded with %r after setting queue tag for %r",
                          response, queue_name)

    _logger.info("Queue attributes were adjusted for all %d queues" % len(queue_names))


def print_help():
    print("Set queue attributes for fabric8-worker.\n"
          "Usage: {} COMMA-SEPARATED-LIST-OF-QUEUES".format(sys.argv[0]))


if __name__ == '__main__':
    if os.getenv('F8A_UNCLOUDED_MODE') in ('1', 'True', 'true'):
        _logger.warning("Worker started in unclouded mode, "
                        "no queue configuration adjustment will be performed")
        sys.exit(0)

    if len(sys.argv) != 2:
        print_help()
        sys.exit(1)

    if sys.argv[1] in ('-h', '--help'):
        print_help()
        sys.exit(0)

    set_queue_attributes(sys.argv[1].split(','))
