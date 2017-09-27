#!/usr/bin/env python
import jsonschema
from celery.utils.log import get_task_logger
from f8a_worker.conf import get_configuration
from selinon import SelinonTask, FatalTaskError
from datetime import datetime
from f8a_worker.schemas import load_worker_schema, set_schema_ref
from f8a_worker.utils import json_serial
from f8a_worker.object_cache import ObjectCache
from f8a_worker.storages import BayesianPostgres
from f8a_worker.storages import PackagePostgres


class BaseTask(SelinonTask):
    description = 'Root of the Task object hierarchy'
    schema_ref = _schema = None
    # set this to False if your task shouldn't get the `_audit` value added to result dict
    add_audit_info = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = get_task_logger(self.__class__.__name__)
        self.configuration = get_configuration()

    @classmethod
    def _strict_assert(cls, assert_cond):
        """Assert on condition, if condition is False, fatal error is raised so
        task is not retried"""
        if not assert_cond:
            raise FatalTaskError("Strict assert failed in task '%s'" % cls.__name__)

    def run(self, node_args):
        # SQS guarantees 'deliver at least once', so there could be multiple
        # messages of a type, give up immediately
        if self.storage and isinstance(self.storage, (BayesianPostgres, PackagePostgres)):
            if self.storage.get_worker_id_count(self.task_id) > 0:
                raise FatalTaskError("Task with ID '%s' was already processed" % self.task_id)

        start = datetime.now()
        try:
            result = self.execute(node_args)
        finally:
            # remove all files that were downloaded for this task
            ObjectCache.wipe()
        end = datetime.now()

        if result:
            # Ensure result complies with the defined schema (if any) before saving
            self.validate_result(result)

        if result is None:
            # Keep track of None results and add _audit and _release keys
            result = {}

        if self.add_audit_info:
            # `_audit` key is added to every analysis info submitted
            result['_audit'] = {
                    'started_at': json_serial(start),
                    'ended_at': json_serial(end),
                    'version': 'v1'
            }

            ecosystem_name = node_args.get('ecosystem')
            result['_release'] = '{}:{}:{}'.format(ecosystem_name,
                                                   node_args.get('name'),
                                                   node_args.get('version'))
        return result

    @classmethod
    def create_test_instance(cls, flow_name=None, task_name=None, parent=None, task_id=None,
                             dispatcher_id=None):
        # used in tests so we do not do ugly things like this, this correctly done by dispatcher
        return cls(flow_name, task_name or cls.__name__, parent, task_id, dispatcher_id)

    def validate_result(self, result):
        """
        Ensures results comply with the task schema, if defined

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

    def execute(self, arguments):
        raise NotImplementedError("Task not implemented")
