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

    def list_available_versions(self, arguments):
        """List all available versions for the given package."""
        object_key = '{ecosystem}/{name}/'.format(**arguments)
        bucket = self._s3.Bucket(self.bucket_name)
        objects = bucket.objects.filter(Prefix=object_key)

        versions = []
        for obj in objects:
            if not obj.key.endswith('.json'):
                continue

            # This simple trick will remove duplicates (subdirs containing task results)
            version_parts = obj.key[len(object_key):-len('.json')].split('/', 1)
            print(version_parts)
            if len(version_parts) == 1:
                versions.append(version_parts[0])

        return versions
