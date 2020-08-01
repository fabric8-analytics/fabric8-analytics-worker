"""Tests covering code in start.py."""

import pytest
import os
import time
from datetime import datetime, timedelta
from f8a_worker.monkey_patch import _check_hung_task

_SQS_MSG_LIFETIME_IN_SEC = (int(os.environ.get('SQS_MSG_LIFETIME', '24')) + 1) * 60 * 60


class TestStartFunctions():
    """Test functions from start.py."""

    def test_check_hung_task(self):
        """Test _check_hung_task."""
        flow_info = {'node_args': {}}
        _check_hung_task(self, flow_info)
        assert flow_info['node_args']['flow_start_time'] is not None

        old_time = time.time() - _SQS_MSG_LIFETIME_IN_SEC
        flow_info = {'node_args': {'flow_start_time': old_time}}
        with pytest.raises(Exception):
            assert _check_hung_task(self, flow_info)
