import json
import logging
from selinon.trace import Trace

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
    Trace.TASK_RESULT_CACHE_HIT,
    # These are not that relevant for prod
    Trace.NODE_FAILURE,
    Trace.NODE_SUCCESSFUL
)


def trace_func(event, report):
    if event in _IGNORED_EVENTS:
        return

    event_str = Trace.event2str(event)
    report.update({'event': event_str})
    # It's OK to use 'extra' here as we are using a custom logging formatter, see celery_settings.py for more info
    if event in Trace.WARN_EVENTS:
        _logger.warning(json.dumps(report))
    else:
        _logger.info(json.dumps(report))
