#!/usr/bin/env python3

from . import AmazonS3


class S3KeywordsSummary(AmazonS3):
    def store(self, node_args, flow_name, task_name, task_id, result):
        object_key = "{ecosystem}/{name}.json".format(**node_args)
        return self.store_dict(result, object_key)
