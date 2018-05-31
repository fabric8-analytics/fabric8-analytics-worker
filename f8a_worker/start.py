#!/usr/bin/env python

"""Start the application."""

import celery
import os
from f8a_worker.setup_celery import init_celery, init_selinon
import raven
from raven.contrib.celery import register_signal, register_logger_signal


class SentryCelery(celery.Celery):
    """Celery class to configure sentry."""

    def on_configure(self):
        """Set up sentry client."""
        dsn = os.environ.get("SENTRY_DSN")
        client = raven.Client(dsn)
        register_logger_signal(client)
        register_signal(client)


def monitor_celery(celery_app):

    state = celery_app.events.State()

    def on_task_started(event):
        state.event(event)
        task = state.tasks.get(event['uuid'])

        print(
            "---",
            "Task started: %s" % task.name,
            "---",
            sep='\n',
        )

    with celery_app.connection() as conn:
        recv = app.events.Receiver(
            conn,
            handlers={
                'task-started': on_task_started,
                '*': state.event,
            }
        )
        recv.capture(limit=None, timeout=None, wakeup=True)


app = SentryCelery('tasks')

# set up celery monitoring
monitor_celery(app)

init_celery(app)
init_selinon(app)

