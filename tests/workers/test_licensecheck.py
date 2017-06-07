# -*- coding: utf-8 -*-

import pytest
import os
import jsonschema
from flexmock import flexmock
from cucoslib.workers import LicenseCheckTask
from cucoslib.schemas import load_worker_schema, pop_schema_ref
from cucoslib.object_cache import EPVCache


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
        results = task.execute(arguments=args)

        assert results is not None
        assert isinstance(results, dict)
        assert results['status'] == 'error'
        task.validate_result(results)

    @pytest.mark.skipif(which("license_check.py") is None,
                        reason="requires license-check RPM")
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

        # Check additional test scan details not covered by schema
        # {'details': {'files': [{'path': 'license.py',
        #                         'result': [{'variant_id': 'lgpl-2.1-s',
        #                                     'license_name': 'LGPLv2',
        #                                     'match': 98}]}],
        #              'license_stats': [{'count': '1',
        #                                 'variant_id': 'lgpl-2.1-s',
        #                                 'license_name': 'LGPLv2'}], ...
        variant_key = "variant_id"
        name_key = "license_name"
        first_stats = results['details']['license_stats'][0]
        assert first_stats[variant_key] == 'lgpl-2.1-s'
        assert first_stats[name_key] == 'LGPLv2'
        file_details = results['details']['files']
        assert len(file_details) > 0
        for entry in file_details:
            assert not os.path.isabs(entry['path'])
        first_file = file_details[0]
        assert first_file['path'] == 'license.py'
        first_file_result = first_file['result'][0]
        assert first_file_result[variant_key] == 'lgpl-2.1-s'
        assert first_file_result[name_key] == 'LGPLv2'
        assert first_file_result['match'] == 98
