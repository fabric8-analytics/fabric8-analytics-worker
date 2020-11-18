"""Initialize package-version level analysis."""
from selinon import FatalTaskError
from f8a_worker.base import BaseTask
import logging

logger = logging.getLogger(__name__)
_SUPPORTED_ECOSYSTEMS = {'golang'}


class NewInitPackageFlow(BaseTask):
    """Initialize package-version-level analysis."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(isinstance(arguments.get('ecosystem'), str))
        self._strict_assert(isinstance(arguments.get('name'), str))
        self._strict_assert(isinstance(arguments.get('version'), str))

        if arguments['ecosystem'] not in _SUPPORTED_ECOSYSTEMS:
            raise FatalTaskError('Unknown ecosystem: %r' % arguments['ecosystem'])

        return arguments
