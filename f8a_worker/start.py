#!/usr/bin/env python

"""Start the application."""

from celery import Celery
from f8a_worker.setup_celery import init_celery, init_selinon


app = Celery('tasks')
init_celery(app)
init_selinon(app)
