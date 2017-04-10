import logging
from selinon.trace import Trace
from cucoslib.conf import is_local_deployment

_logger = logging.getLogger(__name__)


# We don't use caches now
_IGNORED_EVENTS = (
    Trace.NODE_STATE_CACHE_GET,
    Trace.NODE_STATE_CACHE_ADD,
    Trace.NODE_STATE_CACHE_MISS,
    Trace.NODE_STATE_CACHE_HIT,
    Trace.TASK_RESULT_CACHE_GET,
    Trace.TASK_RESULT_CACHE_ADD,
    Trace.TASK_RESULT_CACHE_MISS,
    Trace.TASK_RESULT_CACHE_HIT
)

_WARN_EVENTS = (
    Trace.NODE_FAILURE,
    Trace.TASK_DISCARD_RESULT,
    Trace.TASK_RETRY,
    Trace.TASK_FAILURE,
    Trace.FLOW_FAILURE,
    #Trace.STORAGE_OMIT_STORE_ERROR
)


def trace_func(event, report):
    if event in _IGNORED_EVENTS:
        return

    if 'args' in report:
        # TODO: fix this in Selinon
        report['node_args'] = report.pop('args')

    event_str = Trace.event2str(event)
    report.update({'event': event_str})
    # It's OK to use 'extra' here as we are using a custom logging formatter, see celery_settings.py for more info
    if event in _WARN_EVENTS:
        _logger.warning(event_str, extra=report)
    else:
        _logger.info(event_str, extra=report)
