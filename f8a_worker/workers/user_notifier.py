"""Output: TBD."""

import json

from f8a_worker.base import BaseTask
from f8a_worker.utils import get_session_retry


class UserNotificationTask(BaseTask):
    """Generates report containing descriptive data for dependencies."""
    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self.log.debug("Arguments passed from flow: {}".format(arguments))
        self._strict_assert(arguments.get('dependencies'))
        self._strict_assert(arguments.get('github_repo'))

        return {}
