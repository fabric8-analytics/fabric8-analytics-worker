#!/usr/bin/env python

"""Start the application."""

import celery
import os
from f8a_worker.setup_celery import init_celery, init_selinon
import raven
from raven.contrib.celery import register_signal, register_logger_signal
from f8a_worker.monkey_patch import patched_diapatcher


class SentryCelery(celery.Celery):
    """Celery class to configure sentry."""

    def on_configure(self):
        """Set up sentry client."""
        dsn = os.environ.get("SENTRY_DSN")
        client = raven.Client(dsn)
        register_logger_signal(client)
        register_signal(client)
        client.ignore_exceptions = [
            "f8a_worker.errors.NotABugFatalTaskError",
            "f8a_worker.errors.NotABugTaskError",
            "f8a_worker.errors.TaskAlreadyExistsError"
        ]

        patched_diapatcher()


app = SentryCelery('tasks')
init_celery(app)
init_selinon(app)
