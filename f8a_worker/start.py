#!/usr/bin/env python

"""Start the application."""

import celery
import os
from f8a_worker.setup_celery import init_celery, init_selinon
import raven
from raven.contrib.celery import register_signal, register_logger_signal
from selinon import Dispatcher
from datetime import datetime
import json
from selinon.errors import SelinonException


class NotABugFatalTaskError(SelinonException):
    """An exception that is raised by task on fatal error - task will be not retried."""

    def __init__(self, state):
        """Make sure flow errors capture final state of the flow.

        :param state: final flow details
        """
        super().__init__(json.dumps(state))

    @property
    def state(self):
        """Get structured flow details."""
        return json.loads(str(self))


def _check_hung_task(self, flow_info):
    """Function to remove tasks which are rotating in dispatcher for more than given time.

    :param flow_info: information about the current flow
    """
    node_args = flow_info['node_args']
    if node_args is not None and 'flow_start_time' in node_args \
            and node_args['flow_start_time'] is not None:
        flow_start_time = datetime.strptime(node_args['flow_start_time'], '%Y-%m-%d %H:%M:%S.%f')
        current_time = datetime.now()
        time_diff = current_time - flow_start_time
        # no_of_hours = time_diff.days * 24 + time_diff.seconds // 3600
        no_of_hours = (time_diff.seconds % 3600) // 60
        node_args['no_of_hours'] = no_of_hours
        dispatcher_time_out_in_hrs = int(os.environ.get('DISPATCHER_TIME_OUT_IN_HRS', '24'))

        if no_of_hours >= dispatcher_time_out_in_hrs:
            exc = NotABugFatalTaskError("Flow is running for {} Hours. "
                                        "It is being stopped forcefully. "
                                        "Flow information: {}".format(no_of_hours, flow_info))
            raise self.retry(max_retries=0, exc=exc)
    else:
        # If message is arrived for the first time, then put current time in node arguments
        # and consider it as starting time of the flow.
        node_args['flow_start_time'] = str(datetime.now())


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

        # Monkey Patching "Dispatcher.migrate_message" function to modify code at runtime.
        original_migrate_message = Dispatcher.migrate_message

        def patched_migrate_message(self, flow_info):
            res = original_migrate_message(self, flow_info)
            # adding patch to throw error on message is too old
            _check_hung_task(self, flow_info)
            return res
        Dispatcher.migrate_message = patched_migrate_message


app = SentryCelery('tasks')
init_celery(app)
init_selinon(app)
