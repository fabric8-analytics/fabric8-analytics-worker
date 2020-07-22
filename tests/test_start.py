"""Tests covering code in start.py."""

import pytest
import os
from f8a_worker.start import _check_hung_task
from datetime import datetime, timedelta


class TestStartFunctions():
    """Test functions from start.py."""

    def test_check_hung_task(self):
        """Test _check_hung_task."""
        flow_info = {'node_args': {}}
        _check_hung_task(self, flow_info)
        assert flow_info['node_args']['flow_start_time'] is not None

        time_limit = datetime.now() - timedelta(hours=5)
        flow_info = {'node_args': {'flow_start_time': str(time_limit)}}
        _check_hung_task(self, flow_info)
        assert flow_info['node_args']['flow_start_time'] is not None
        assert flow_info['node_args']['no_of_hours'] == 5

        dispatcher_time_out_in_hrs = int(os.environ.get('DISPATCHER_TIME_OUT_IN_HRS', '24')) + 2

        time_limit = datetime.now() - timedelta(hours=dispatcher_time_out_in_hrs + 2)
        flow_info = {'node_args': {'flow_start_time': str(time_limit)}}
        with pytest.raises(Exception):
            assert _check_hung_task(self, flow_info)
