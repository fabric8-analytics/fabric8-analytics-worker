# -*- coding: utf-8 -*-

"""Tests for the LinguistTask worker task."""

from os.path import isfile
import pytest
from flexmock import flexmock
from f8a_worker.object_cache import EPVCache
from f8a_worker.enums import EcosystemBackend
from f8a_worker.workers import LinguistTask
from f8a_worker.models import Ecosystem
from f8a_worker.process import IndianaJones

ECOSYSTEM = Ecosystem(name='pypi', backend=EcosystemBackend.pypi)
MODULE_NAME = 'six'
MODULE_VERSION = '1.10.0'


@pytest.mark.usefixtures("dispatcher_setup")
class TestLinguist(object):
    """Tests for the LinguistTask worker task."""

    @pytest.mark.skipif(not isfile('/usr/local/bin/linguist'),
                        reason="requires linguist")
    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self, tmpdir):
        """Start the LinguistTask worker task and check its results."""
        # TODO: reduce cyclomatic complexity
        IndianaJones.fetch_artifact(
            ecosystem=ECOSYSTEM, artifact=MODULE_NAME,
            version=MODULE_VERSION, target_dir=str(tmpdir))

        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(str(tmpdir))
        task = LinguistTask.create_test_instance(task_name='languages')
        results = task.execute(args)

        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        details = results['details']
        assert len(details) > 3  # tarball, setup.py, LICENSE, README, etc.
        for f in details:
            if f.get('path') and f['path'].endswith('six.py'):
                # {'output': {'language': 'Python',
                #             'lines': '869',
                #             'mime': 'application/x-python',
                #             'sloc': '869',
                #             'type': 'Text'},
                #  'path': 'six-1.10.0/six.py',
                #  'type': ['Python script, ASCII text executable']},
                assert set(f.keys()) == {'output', 'path', 'type'}
                assert set(f['output'].keys()) == {'language', 'lines', 'mime', 'sloc', 'type'}
                assert f['output']['language'] == 'Python'
                assert f['type'].pop().startswith('Python')
        assert results['status'] == 'success'
