#!/usr/bin/env python

import logging
from celery import Celery
from f8a_worker.setup_celery import init_celery

# remove too verbose logs from third-party libraries
logging.getLogger('boto').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

app = Celery('tasks')
init_celery(app)
