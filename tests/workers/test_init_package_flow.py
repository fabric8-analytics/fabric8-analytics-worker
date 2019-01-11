"""Tests for the InitPackageFlow task."""

import pytest
from selinon import FatalTaskError

from f8a_worker.workers import InitPackageFlow


@pytest.mark.usefixtures("dispatcher_setup")
class TestInitPackageFlow(object):
    """Tests for the class InitPackageFlow."""

    @pytest.mark.parametrize('args', [
        {'ecosystem': 'maven', 'name': None, 'version': '0.1.25'},
        {'ecosystem': ['maven'], 'name': 'gid:aid', 'version': '0.1.25'},
        {'name': 'gid:aid', 'version': '0.1.25'}
    ])
    def test_basic_input_validation(self, args):
        """Check that the tasks performs basic input validations."""
        task = InitPackageFlow.create_test_instance(task_name='package_init_task')

        with pytest.raises(FatalTaskError):
            task.execute(arguments=args)
