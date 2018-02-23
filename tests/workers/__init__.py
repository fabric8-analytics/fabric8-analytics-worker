"""Tests for all worker types."""


def instantiate_task(cls, task_name=None):
    """Instantiates task object from given class.

    :param cls: class to be instantiated
    :param task_name: str, task name
    :return: object of a type `cls`
    """

    return cls(flow_name=None,
               task_name=task_name or cls.__name__,
               parent=None,
               task_id=None,
               dispatcher_id=None)
