"""Functions for Monkey Patching in Selinon."""

from datetime import datetime
import json
from selinon.errors import SelinonException
from selinon import Dispatcher
import os


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
    """Remove tasks which are rotating in dispatcher for more than given time.

    :param flow_info: information about the current flow
    """
    node_args = flow_info['node_args']
    if node_args is not None and 'flow_start_time' in node_args \
            and node_args['flow_start_time'] is not None:
        flow_start_time = datetime.strptime(node_args['flow_start_time'], '%Y-%m-%d %H:%M:%S.%f')
        current_time = datetime.now()
        time_diff = current_time - flow_start_time
        no_of_hours = time_diff.days * 24 + time_diff.seconds // 3600

        node_args['no_of_hours'] = no_of_hours
        dispatcher_time_out_in_hrs = int(os.environ.get('SQS_MSG_LIFETIME', '24'))

        if no_of_hours >= dispatcher_time_out_in_hrs:
            exc = NotABugFatalTaskError("Flow is running for {} Hours. "
                                        "It is being stopped forcefully. "
                                        "Flow information: {}".format(no_of_hours, flow_info))
            raise self.retry(max_retries=0, exc=exc)
    else:
        # If message is arrived for the first time, then put current time in node arguments
        # and consider it as starting time of the flow.
        node_args['flow_start_time'] = str(datetime.now())


def patched_diapatcher(self):
    """Monkey Patching "Dispatcher.migrate_message" function to modify code at runtime."""
    original_migrate_message = Dispatcher.migrate_message

    def patched_migrate_message(self, flow_info):
        res = original_migrate_message(self, flow_info)
        # adding patch to throw error on message is too old
        _check_hung_task(self, flow_info)
        return res

    Dispatcher.migrate_message = patched_migrate_message
