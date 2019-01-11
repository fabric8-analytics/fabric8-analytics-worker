"""Tests for the InitAnalysisFlow task."""

import pytest
from selinon import FatalTaskError

from f8a_worker.workers import InitAnalysisFlow


@pytest.mark.usefixtures("dispatcher_setup")
class TestInitAnalysisFlow(object):
    """Tests for the class InitAnalysisFlow."""

    @pytest.mark.parametrize('args', [
        {'ecosystem': 'maven', 'name': 'gid:aid', 'version': {'latest': '0.1.25'}},
        {'ecosystem': 'maven', 'name': None, 'version': '0.1.25'},
        {'ecosystem': ['maven'], 'name': 'gid:aid', 'version': '0.1.25'},
        {'name': 'gid:aid', 'version': '0.1.25'}
    ])
    def test_basic_input_validation(self, args):
        """Check that the tasks performs basic input validations."""
        task = InitAnalysisFlow.create_test_instance(task_name='init_task')

        with pytest.raises(FatalTaskError):
            task.execute(arguments=args)
