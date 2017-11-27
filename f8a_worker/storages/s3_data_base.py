#!/usr/bin/env python3

import json
import botocore
from f8a_worker.utils import json_serial
from . import AmazonS3


class S3DataBase(AmazonS3):
    @staticmethod
    def _base_file_content(old_file_content, result):
        # remove entries we don't want to keep
        result.pop('access_count', None)
        # do not keep track of tasks that were used for Selinon's Dispatcher book-keeping
        analyses_list = (set(old_file_content.get('analyses', [])) |
                         set(result.get('analyses', {}).keys()))
        analyses_list = [a for a in analyses_list if not a[0].isupper()]

        content = result
        content['analyses'] = analyses_list
        if 'finished_at' in content:
            content['finished_at'] = json_serial(content['finished_at'])
        if 'started_at' in content:
            content['started_at'] = json_serial(content['started_at'])

        return content

    @staticmethod
    def _construct_base_file_name(arguments):
        """Construct location of EPV in the bucket.

        :param arguments: arguments as passed to the flow
        :return: str, EPV location in the bucket
        """
        raise NotImplementedError()

    def list_available_task_results(self, arguments):
        """Get names of all task results stored on S3."""
        object_key = self._construct_base_file_name(arguments)
        bucket = self._s3.Bucket(self.bucket_name)
        objects = bucket.objects.filter(Prefix=object_key)

        # TODO: this will return way too many results, we should optimize this by using tags or RDS for example
        task_names = []
        for obj in objects:
            if not obj.key.endswith('.json'):
                continue

            task_name = obj.key[len(object_key) + 1:-len('.json')].split('/', 1)[0]
            if task_name:
                task_names.append(task_name)

        return task_names

    def list_available_names(self, ecosystem, prefix=None):
        """Get all available names under given ecosystem."""
        object_key = '{}/{}'.format(ecosystem, prefix or '')
        bucket = self._s3.Bucket(self.bucket_name)
        objects = bucket.objects.filter(Prefix=object_key)

        names = set()
        # TODO: this will return way too many results, we should optimize this by using tags or RDS for example
        for entry in objects:
            name = entry.key[len(ecosystem) + 1:].split('/', 1)[0]

            if name.endswith('.json'):
                name = name[:-len('.json')]

            names.add(name)

        return list(names)

    @classmethod
    def _construct_task_result_object_key(cls, arguments, task_name):
        """Construct object key on S3 for a task_result.

        :param arguments: arguments as passed to the flow
        :param task_name: name of the task for which the key should be constructed
        :return: fully qualified path to the task result"""
        base_file_name = cls._construct_base_file_name(arguments)
        return "{base_file_name}/{task_name}.json".format(base_file_name=base_file_name,
                                                          task_name=task_name)

    def store_base_file_record(self, arguments, result):
        """Add info about analyses available.

        :param arguments: flow arguments
        :param result: flow result - JSON describing whole analyses result
        :return: base file record version identifier
        """
        # There available a top level JSON file located at:
        #
        #   <ecosystem>/<package_name>/<version>.json
        #
        # that stores JSON in where tasks are available under 'tasks' key:
        #
        #  {'tasks': [ 'digests', 'metadata', ...]}
        #
        base_file_name = "{}.json".format(self._construct_base_file_name(arguments))

        try:
            file_content = self.retrieve_blob(base_file_name)
            # if we have file that is empty, let's overwrite it
            file_content = json.loads(file_content.decode() or '{}')
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'NoSuchKey':
                # we are inserting for the first time, assign whole content
                file_content = {}
            else:
                # Some another error, not no such file
                raise

        # we keep track only of tasks that were run, so keep only keys
        file_content = self._base_file_content(file_content, result)
        return self.store_dict(file_content, base_file_name)

    def store_task_result(self, arguments, task_name, task_result):
        """Store result of a task on S3.

        :param arguments: flow arguments
        :param task_name: name of the task for which result should be stored
        :param task_result: task result
        :return: base file version identifier
        """
        object_key = self._construct_task_result_object_key(arguments, task_name)
        return self.store_dict(task_result, object_key)
