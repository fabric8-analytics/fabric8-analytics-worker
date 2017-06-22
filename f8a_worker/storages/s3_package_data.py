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

    def retrieve_task_result(self, ecosystem, name, task_name):
        """Retrieve task result stored on S3 for the given EPV.

        :param ecosystem: ecosystem name
        :param name: package name
        :param task_name: task name
        :return: task results as stored on S3
        """
        object_key = self._construct_task_result_object_key(locals(), task_name)
        return self.retrieve_dict(object_key)
