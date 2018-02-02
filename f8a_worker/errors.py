"""Declaration of classes representing various exception types."""


class TaskError(Exception):
    """There was an error during task execution."""


class F8AConfigurationException(Exception):
    """There was an error during handling configuration."""
