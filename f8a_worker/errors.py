"""Declaration of classes representing various exception types."""
from selinon import FatalTaskError


class TaskError(Exception):
    """There was an error during task execution."""


class NonCriticalTaskError(TaskError):
    """There was an error during task execution."""


class F8AConfigurationException(Exception):
    """There was an error during handling configuration."""


class TaskAlreadyExistsError(FatalTaskError):
    """Requested task result is already saved in the database."""
