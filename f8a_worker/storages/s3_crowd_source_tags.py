#!/usr/bin/env python3

from . import AmazonS3


class S3CrowdSourceTags(AmazonS3):

    def _construct_object_key(self, arguments):
        path = self.get_object_key_path(arguments['ecosystem'])
        return "{path}/crowd_sourcing_package_topic.json".format(path=path)

    @staticmethod
    def get_object_key_path(ecosystem):
        return "{ecosystem}".format(ecosystem=ecosystem) + "github/data_input_raw_package_list/"

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args

        object_key = self._construct_object_key(node_args)
        self.store_dict(result, object_key)
        return
