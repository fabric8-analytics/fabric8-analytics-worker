#!/usr/bin/env python

"""Start the application."""

import celery
import os
from f8a_worker.setup_celery import init_celery, init_selinon
from raven.contrib.celery import register_signal, register_logger_signal


class Celery(celery.Celery):
    """Celery class to configure sentry."""

    def on_configure(self):
        """Set up sentry client."""
        dsn = os.environ.get("SENTRY_DSN")
        client = raven.Client(dsn)
        register_logger_signal(client)
        register_signal(client)


app = Celery('tasks')
init_celery(app)
init_selinon(app)
