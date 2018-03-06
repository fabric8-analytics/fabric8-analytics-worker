# -*- coding: utf-8 -*-

"""Tests for the BinwalkTask worker task."""

import os
import pytest
from flexmock import flexmock
from f8a_worker.object_cache import EPVCache
from f8a_worker.workers import BinwalkTask


def is_executable(fpath):
    """Check if the given file is executable."""
    return os.path.isfile(fpath) and os.access(fpath, os.X_OK)


@pytest.mark.usefixtures("dispatcher_setup")
class TestBinwalk(object):
    """Tests for the BinwalkTask worker task."""

    @pytest.mark.skipif(not os.path.isfile('/usr/bin/binwalk'),
                        reason="requires binwalk")
    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self):
        """Start the BinwalkTask worker task and test its result."""
        path = os.path.join(
                   os.path.dirname(
                       os.path.abspath(__file__)), '..', '..', 'hack')  # various executable scripts
        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_source_tarball').and_return(path)
        task = BinwalkTask.create_test_instance(task_name='binary_data')
        results = task.execute(arguments=args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results['details']
        # {'details': [{'output': ['Executable script, shebang: "/usr/bin/bash"'],
        #               'path': 'workers.sh'}]}
        for f in details:
            if f['path'].endswith('.sh') and is_executable(os.path.join(path, f['path'])):
                assert f['output'][0].startswith('Executable')
                break
        assert results['status'] == 'success'
