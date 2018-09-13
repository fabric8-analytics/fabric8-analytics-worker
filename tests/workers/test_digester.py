# -*- coding: utf-8 -*-

"""Tests for the class DigesterTask."""

from __future__ import unicode_literals
import pytest
from flexmock import flexmock

from f8a_worker.object_cache import EPVCache
from f8a_worker.workers import DigesterTask
from f8a_worker.process import IndianaJones
from f8a_worker.utils import compute_digest

PYPI_MODULE_NAME = "six"
PYPI_MODULE_VERSION = "1.0.0"


@pytest.mark.usefixtures("dispatcher_setup")
class TestDigester(object):
    """Tests for the class DigesterTask."""

    @pytest.mark.usefixtures("no_s3_connection")
    def test_execute(self, tmpdir, pypi):
        """Check the method DigesterTask.execute()."""
        artifact_digest, artifact_path = IndianaJones.fetch_artifact(
            pypi, artifact=PYPI_MODULE_NAME,
            version=PYPI_MODULE_VERSION, target_dir=str(tmpdir))

        args = dict.fromkeys(('ecosystem', 'name', 'version'), 'some-value')
        # flexmock(EPVCache).should_receive('get_extracted_source_tarball').and_return(str(tmpdir))
        flexmock(EPVCache).should_receive('get_source_tarball').and_return(artifact_path)
        task = DigesterTask.create_test_instance(task_name='digests')
        results = task.execute(arguments=args)

        assert results is not None
        assert isinstance(results, dict)
        assert set(results.keys()) == {'details', 'status', 'summary'}
        artifact_details = None
        for details in results['details']:
            assert {'sha256', 'sha1', 'md5', 'ssdeep', 'path'}.issubset(set(details.keys()))
            if details.get('artifact'):
                artifact_details = details
        # there are artifact details
        assert artifact_details is not None
        # the artifact digest which Indy returns is the same as the one from DigesterTask
        assert artifact_digest == artifact_details['sha256'] == compute_digest(artifact_path)
        assert artifact_details['path'] == 'six-1.0.0.tar.gz'
