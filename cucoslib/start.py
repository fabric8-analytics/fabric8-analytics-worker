#!/usr/bin/env python

from celery import Celery
from cucoslib.setup_celery import init_celery, init_selinon


app = Celery('tasks')
init_celery(app)
init_selinon(app)
