#!/usr/bin/env python3

from . import AmazonS3


class S3Readme(AmazonS3):
    @staticmethod
    def _construct_object_key(arguments):
        return "{ecosystem}/{package}/README.json".format(ecosystem=arguments['ecosystem'],
                                                          package=arguments['name'])

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args
        assert 'name' in node_args
        assert 'version' in node_args

        object_key = self._construct_object_key(node_args)
        self.store_dict(result, object_key)

        return "{}:{}".format(self.bucket_name, object_key)
