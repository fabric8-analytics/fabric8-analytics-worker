#!/usr/bin/env python3

from .s3_data_base import S3DataBase


class S3Data(S3DataBase):
    @staticmethod
    def _construct_base_file_name(arguments):
        """Construct location of EPV in the bucket.

        :param arguments: arguments as passed to the flow
        :return: str, EPV location in the bucket
        """
        assert 'ecosystem' in arguments
        assert 'name' in arguments
        assert 'version' in arguments
        return "{ecosystem}/{name}/{version}".format(**arguments)

    def construct_task_result_object_key(self, ecosystem, name, version, task_name):
        """Get object key for task result stored on S3."""
        return self._construct_task_result_object_key({
            'ecosystem': ecosystem,
            'name': name,
            'version': version
        }, task_name)

    def retrieve_task_result(self, ecosystem, name, version, task_name, object_version_id=None):
        """Retrieve task result stored on S3 for the given EPV.

        :param ecosystem: ecosystem name
        :param name: package name
        :param version: package version
        :param task_name: task name
        :param object_version_id: version id of retrieved object, None for latest
        :return: task results as stored on S3
        """
        return self.retrieve_task_result_args(locals(), task_name, object_version_id)

    def retrieve_task_result_args(self, arguments, task_name, object_version_id=None):
        """Retrieve task result stored on S3 for the given EPV.

        :param arguments: arguments supplied to the flow
        :param task_name: task name
        :param object_version_id: version id of retrieved object, None for latest
        :return: task results as stored on S3
        """
        object_key = self._construct_task_result_object_key(arguments, task_name)
        return self.retrieve_dict(object_key, object_version_id)
