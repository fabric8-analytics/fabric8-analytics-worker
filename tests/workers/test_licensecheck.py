# -*- coding: utf-8 -*-

"""Tests for the LicenseCheckTask worker task."""

import jsonschema
from flexmock import flexmock
from pathlib import Path
import pytest

from f8a_worker.workers import LicenseCheckTask
from f8a_worker.schemas import load_worker_schema, pop_schema_ref
from f8a_worker.object_cache import EPVCache


@pytest.mark.offline
@pytest.mark.usefixtures("dispatcher_setup")
class TestLicenseCheck(object):
    """Tests for the LicenseCheckTask worker task."""

    @pytest.mark.usefixtures("no_s3_connection")
    def test_error(self):
        """Start the LicenseCheckTask worker task with improper parameters and test its results."""
        data = "/this-is-not-a-real-directory"
        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_sources').and_return(data)
        task = LicenseCheckTask.create_test_instance(task_name='source_licenses')
        with pytest.raises(Exception):
            task.execute(arguments=args)

    @pytest.mark.skipif(not Path('/opt/scancode-toolkit/scancode').is_file(),
                        reason="requires scancode")
    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self):
        """Start the LicenseCheckTask task and test its results."""
        data = str(Path(__file__).parent.parent / 'data/license')
        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_sources').and_return(data)
        task = LicenseCheckTask.create_test_instance(task_name='source_licenses')
        results = task.execute(arguments=args)

        assert results is not None
        assert isinstance(results, dict)
        assert results['status'] == 'success'
        # Check task self-validation
        task.validate_result(results)

        # Check scan consumer validation
        schema_ref = pop_schema_ref(results)
        schema = load_worker_schema(schema_ref)
        jsonschema.validate(results, schema)

        short_name = 'LGPL 2.1 or later'
        details = results['details']
        assert details.get('files_count') is not None and details.get('files_count') > 0
        assert short_name in details.get('licenses', {})
        summary = results['summary']
        assert short_name in summary.get('sure_licenses', [])
