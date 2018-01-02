#!/usr/bin/env python3

from .s3_data_base import S3DataBase


class S3PackageData(S3DataBase):
    @staticmethod
    def _construct_base_file_name(arguments):
        """Construct location of EPV in the bucket.

        :param arguments: arguments as passed to the flow
        :return: str, ecosystem-package location in the bucket
        """
        assert 'ecosystem' in arguments
        assert 'name' in arguments
        return "{ecosystem}/{name}".format(**arguments)

    def construct_task_result_object_key(self, ecosystem, name, task_name):
        """Get object key for task result stored on S3."""
        return self._construct_task_result_object_key({
            'ecosystem': ecosystem,
            'name': name,
        }, task_name)

    def retrieve_task_result(self, ecosystem, name, task_name, version_id=None):
        """Retrieve task result stored on S3 for the given EPV.

        :param ecosystem: ecosystem name
        :param name: package name
        :param task_name: task name
        :param version_id: S3 version identifier for stored task results
        :return: task results as stored on S3
        """
        object_key = self._construct_task_result_object_key(locals(), task_name)
        return self.retrieve_dict(object_key, version_id)
