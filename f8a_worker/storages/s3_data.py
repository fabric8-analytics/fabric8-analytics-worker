#!/usr/bin/env python3

"""Use S3 for package-version level tasks` results."""

from .s3_data_base import S3DataBase


class S3Data(S3DataBase):
    """Use S3 for package-version level tasks` results."""

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

    def retrieve_task_result(self, ecosystem, name, version, task_name):
        """Retrieve task result stored on S3 for the given EPV.

        :param ecosystem: ecosystem name
        :param name: package name
        :param version: package version
        :param task_name: task name
        :return: task results as stored on S3
        """
        object_key = self._construct_task_result_object_key(locals(), task_name)
        return self.retrieve_dict(object_key)
