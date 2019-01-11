#!/usr/bin/env python

"""Base class for selinon tasks."""

import sys
import jsonschema
from celery.utils.log import get_task_logger
from f8a_worker.defaults import configuration
from selinon import SelinonTask, FatalTaskError
from datetime import datetime

from f8a_worker.errors import TaskAlreadyExistsError
from f8a_worker.schemas import load_worker_schema, set_schema_ref
from f8a_worker.utils import json_serial
from f8a_worker.object_cache import ObjectCache
from f8a_worker.storages import BayesianPostgres
from f8a_worker.storages import PackagePostgres


class BaseTask(SelinonTask):
    """Base class for selinon tasks."""

    description = 'Root of the Task object hierarchy'
    schema_ref = _schema = None
    # set this to False if your task shouldn't get the `_audit` value added to result dict
    add_audit_info = True

    def __init__(self, *args, **kwargs):
        """Initialize object."""
        super().__init__(*args, **kwargs)
        self.log = get_task_logger(self.__class__.__name__)
        self.configuration = configuration

    @classmethod
    def _strict_assert(cls, assert_cond):
        """Assert on condition.

        If condition is False, fatal error is raised so task is not retried.
        """
        if not assert_cond:
            raise FatalTaskError("Strict assert failed in task '%s'" % cls.__name__)

    @staticmethod
    def _add_audit_info(task_result: dict,
                        task_start: datetime,
                        task_end: datetime,
                        node_args):
        """Add the audit and release information to the result dictionary.

        :param task_result: dict, task result
        :param task_start: datetime, the start of the task
        :param task_end: datetime, the end of the task
        :param node_args: arguments passed to flow/node
        """
        task_result['_audit'] = {
            'started_at': json_serial(task_start),
            'ended_at': json_serial(task_end),
            'version': 'v1'
        }

        ecosystem_name = node_args.get('ecosystem')
        task_result['_release'] = '{}:{}:{}'.format(ecosystem_name,
                                                    node_args.get('name'),
                                                    node_args.get('version'))

    def run(self, node_args):
        """To be transparently called by Selinon.

        Selinon transparently calls run(), which takes care of task audit and
        some additional checks and calls execute().
        """
        # SQS guarantees 'deliver at least once', so there could be multiple
        # messages of a type, give up immediately
        if self.storage and isinstance(self.storage, (BayesianPostgres, PackagePostgres)):
            if self.storage.get_worker_id_count(self.task_id) > 0:
                raise TaskAlreadyExistsError("Task with ID '%s'"
                                             " was already processed" % self.task_id)

        start = datetime.utcnow()
        try:
            result = self.execute(node_args)

        except Exception as exc:
            if self.add_audit_info:
                # `_audit` key is added to every analysis info submitted
                end = datetime.utcnow()
                result = dict()

                self._add_audit_info(
                    task_result=result,
                    task_start=start,
                    task_end=end,
                    node_args=node_args,
                )

                # write the audit info to the storage
                self.storage.store_error(
                    node_args=node_args,
                    flow_name=self.flow_name,
                    task_name=self.task_name,
                    task_id=self.task_id,
                    exc_info=sys.exc_info(),
                    result=result
                )

            raise exc

        finally:
            # remove all files that were downloaded for this task
            ObjectCache.wipe()

        end = datetime.utcnow()

        if result:
            # Ensure result complies with the defined schema (if any) before saving
            self.validate_result(result)

        if result is None:
            # Keep track of None results and add _audit and _release keys
            result = {}

        if self.add_audit_info:
            # `_audit` key is added to every analysis info submitted
            self._add_audit_info(
                task_result=result,
                task_start=start,
                task_end=end,
                node_args=node_args,
            )

        return result

    @classmethod
    def create_test_instance(cls, flow_name=None, task_name=None, parent=None, task_id=None,
                             dispatcher_id=None):
        """Create instance of task for tests."""
        # used in tests so we do not do ugly things like this, this correctly done by dispatcher
        return cls(flow_name, task_name or cls.__name__, parent, task_id, dispatcher_id)

    def validate_result(self, result):
        """Ensure that results comply with the task schema, if defined.

        Tasks define a schema by setting schema_ref appropriately.
        Schemas are retrieved from workers/schemas/generated via pkgutil.
        """
        # Skip validation if no schema is defined
        schema_ref = self.schema_ref
        if schema_ref is None:
            return
        # Load schema if not yet loaded
        schema = self._schema
        if schema is None:
            schema = self._schema = load_worker_schema(schema_ref)
        # Validate result against schema
        jsonschema.validate(result, schema)
        # Record the validated schema details
        set_schema_ref(result, schema_ref)

    def execute(self, _arguments):
        """Return dictionary with results - must be implemented by any subclass."""
        raise NotImplementedError("Task not implemented")
