# -*- coding: utf-8 -*-

import pytest
import os
import jsonschema
from flexmock import flexmock
from f8a_worker.workers import LicenseCheckTask
from f8a_worker.schemas import load_worker_schema, pop_schema_ref
from f8a_worker.object_cache import EPVCache


# TODO: drop the try/except after switching to Python 3
try:
    from shutil import which
except ImportError:
    # Near-enough-for-our-purposes equivalent in Python 2.x
    from distutils.spawn import find_executable as which


@pytest.mark.offline
@pytest.mark.usefixtures("dispatcher_setup")
class TestLicenseCheck(object):

    @pytest.mark.usefixtures("no_s3_connection")
    def test_error(self):
        data = "/this-is-not-a-real-directory"
        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_sources').and_return(data)
        task = LicenseCheckTask.create_test_instance(task_name='source_licenses')
        with pytest.raises(Exception):
            results = task.execute(arguments=args)

    @pytest.mark.skipif(not os.path.isfile('/opt/scancode-toolkit/scancode'),
                        reason="requires scancode")
    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self):
        data = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)), '..', 'data', 'license')
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
