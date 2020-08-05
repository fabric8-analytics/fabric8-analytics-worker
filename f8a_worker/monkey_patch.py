"""Functions for Monkey Patching in Selinon."""

import time
import os
from selinon import Dispatcher
from f8a_worker.errors import NotABugFatalTaskError

_SQS_MSG_LIFETIME_IN_SEC = int(os.environ.get('SQS_MSG_LIFETIME', '24')) * 60 * 60


def _check_hung_task(self, flow_info):
    """Remove tasks which are rotating in dispatcher for more than given time.

    :param flow_info: information about the current flow
    """
    node_args = flow_info['node_args']
    flow_start_time = node_args.get('flow_start_time', 0)
    if flow_start_time > 0:
        now = time.time()
        if now - flow_start_time > _SQS_MSG_LIFETIME_IN_SEC:
            exc = NotABugFatalTaskError("Flow could not be completed in configured time limit. "
                                        "It is being stopped forcefully. "
                                        "Flow information: {}".format(flow_info))
            raise self.retry(max_retries=0, exc=exc)
    else:
        # If message is arrived for the first time, then put current time in node arguments
        # and consider it as starting time of the flow.
        node_args['flow_start_time'] = time.time()


def patch(self):
    """Monkey Patching "Dispatcher.migrate_message" function to modify code at runtime."""
    original_migrate_message = Dispatcher.migrate_message

    def patched_migrate_message(self, flow_info):
        res = original_migrate_message(self, flow_info)
        # Adding patch to throw error if the message is older than SQS_MSG_LIFETIME
        _check_hung_task(self, flow_info)
        return res

    Dispatcher.migrate_message = patched_migrate_message
