"""Declaration of classes representing various exception types."""
from selinon import FatalTaskError


class TaskError(Exception):
    """There was an error during task execution."""


class NotABugTaskError(TaskError):
    """Task error, but not a bug in the code.

    This exception will be ignored by Sentry.
    """


class NotABugFatalTaskError(FatalTaskError):
    """Task error, but not a bug in the code. Retry won't help.

    This exception will be ignored by Sentry.
    """


class F8AConfigurationException(Exception):
    """There was an error during handling configuration."""


class TaskAlreadyExistsError(FatalTaskError):
    """Requested task result is already saved in the database."""
