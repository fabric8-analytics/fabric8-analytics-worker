#!/usr/bin/env python3

from . import AmazonS3


class S3Readme(AmazonS3):
    @staticmethod
    def _construct_object_key(**arguments):
        return "{ecosystem}/{name}/README.json".format(**arguments)

    def retrieve_readme_json(self, ecosystem, name):
        object_key = self._construct_object_key(ecosystem=ecosystem, name=name)
        return self.retrieve_dict(object_key)

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args
        assert 'name' in node_args

        object_key = self._construct_object_key(**node_args)
        self.store_dict(result, object_key)

        return "{}:{}".format(self.bucket_name, object_key)
