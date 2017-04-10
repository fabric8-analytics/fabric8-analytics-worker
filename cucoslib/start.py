#!/usr/bin/env python

import logging
from celery import Celery
from cucoslib.setup_celery import init_celery


app = Celery('tasks')
init_celery(app)
