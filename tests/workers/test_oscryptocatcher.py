# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import pytest
from flexmock import flexmock
from f8a_worker.workers import OSCryptoCatcherTask
from f8a_worker.object_cache import EPVCache


@pytest.mark.usefixtures("dispatcher_setup")
class TestOSCryptoCatcher(object):
    @pytest.mark.skipif(not os.path.isfile('/usr/bin/oscryptocatcher'),
                        reason="requires oscryptocatcher")
    @pytest.mark.usefixtures("no_s3_connection")
    def test_ssl_py(self):
        path = sys.modules['ssl'].__file__  # /usr/lib64/python2.7/ssl.pyc
        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(path)
        task = OSCryptoCatcherTask.create_test_instance(task_name='crypto_algorithms')
        results = task.execute(arguments=args)

        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results['details'].pop()
        assert set(details.keys()) == {'crypto',
                                       'file',
                                       'matchtype'}
        assert details['crypto'] == 'SSL'
        assert not os.path.isabs(details['file'])
        assert results['summary']['filename'] == [{"name": "SSL", "count": 1}]
        assert results['status'] == 'success'
