#!/usr/bin/env python3

import json
import botocore
from f8a_worker.utils import json_serial
from . import AmazonS3


class S3Data(AmazonS3):
    @staticmethod
    def _construct_base_file_name(ecosystem, name, version):
        """Construct location of EPV in the bucket"""
        return "{ecosystem}/{name}/{version}".format(ecosystem=ecosystem, name=name, version=version)

    @classmethod
    def _construct_task_result_object_key(cls, ecosystem, name, version, task_name):
        """Construct object key on S3 for a task_result for the given EPV"""
        base_file_name = cls._construct_base_file_name(ecosystem, name, version)
        return "{base_file_name}/{task_name}.json".format(base_file_name=base_file_name, task_name=task_name)

    @staticmethod
    def _base_file_content(old_file_content, result):
        # remove entries we don't want to keep
        result.pop('access_count', None)
        # do not keep track of tasks that were used for Selinon's Dispatcher book-keeping
        analyses_list = set(old_file_content.get('analyses', [])) | set(result.get('analyses', {}).keys())
        analyses_list = [a for a in analyses_list if not a[0].isupper()]

        content = result
        content['analyses'] = analyses_list
        if 'finished_at' in content:
            content['finished_at'] = json_serial(content['finished_at'])
        if 'started_at' in content:
            content['started_at'] = json_serial(content['started_at'])

        return content

    def store_base_file_record(self, arguments, result):
        """ Add info about analyses available for the given EPV

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
        assert 'name' in arguments
        assert 'version' in arguments
        assert 'ecosystem' in arguments

        base_file_name = "{}.json".format(self._construct_base_file_name(arguments['ecosystem'],
                                                                         arguments['name'],
                                                                         arguments['version']))

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
        """ Store result of a task on S3

        :param arguments: flow arguments
        :param task_name: name of the task for which result should be stored
        :param task_result: task result
        :return: base file version identifier
        """
        # For the given EPV, the path to task result is:
        #
        #   <ecosystem>/<package_name>/<version>/<task_name>.json
        #
        assert 'ecosystem' in arguments
        assert 'name' in arguments
        assert 'version' in arguments

        object_key = self._construct_task_result_object_key(arguments['ecosystem'],
                                                            arguments['name'],
                                                            arguments['version'],
                                                            task_name)
        return self.store_dict(task_result, object_key)

    def retrieve_task_result(self, ecosystem, name, version, task_name):
        """ Retrieve task result stored on S3

        :param ecosystem: ecosystem name
        :param name: package name
        :param version: package version
        :param task_name: task name
        :return: task results as stored on S3
        """
        object_key = self._construct_task_result_object_key(ecosystem,
                                                            name,
                                                            version,
                                                            task_name)
        return self.retrieve_dict(object_key)

