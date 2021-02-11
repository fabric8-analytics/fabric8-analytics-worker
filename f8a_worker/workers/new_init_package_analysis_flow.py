"""Initialize package level analysis."""
from selinon import FatalTaskError
from f8a_worker.base import BaseTask
import logging
from f8a_utils.versions import is_pkg_public
from f8a_worker.errors import NotABugFatalTaskError

logger = logging.getLogger(__name__)
_SUPPORTED_ECOSYSTEMS = {'golang'}


class NewInitPackageAnlysisFlow(BaseTask):
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

        # Don't ingest for private packages
        if not is_pkg_public(arguments['ecosystem'], arguments['name']):
            logger.info("Private package ingestion ignored %s %s",
                        arguments['ecosystem'], arguments['name'])
            raise NotABugFatalTaskError("Private package alert {} {}".format(
                arguments['ecosystem'], arguments['name']))

        return arguments
