"""Initialize package level analysis."""
from selinon import FatalTaskError
from f8a_worker.base import BaseTask
from f8a_worker.workers.init_package_flow import validate_url
import logging

logger = logging.getLogger(__name__)
_SUPPORTED_ECOSYSTEMS = {'golang'}


class NewInitPackageFlow(BaseTask):
    """Initialize package-level analysis."""

    def execute(self, arguments):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(isinstance(arguments.get('ecosystem'), str))
        self._strict_assert(isinstance(arguments.get('name'), str))

        if arguments['ecosystem'] not in _SUPPORTED_ECOSYSTEMS:
            raise FatalTaskError('Unknown ecosystem: %r' % arguments['ecosystem'])

        if 'url' not in arguments:
            raise FatalTaskError('Github URL is not found in node arguments')

        # Checking for github url validation
        arguments['url'] = validate_url(arguments['url'])

        return arguments
