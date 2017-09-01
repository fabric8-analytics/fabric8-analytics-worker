#!/usr/bin/env python3

from . import AmazonS3


class S3Manifests(AmazonS3):
    @staticmethod
    def _construct_object_key(node_args, manifest):
        assert 'filename' in manifest
        return "{}/{}".format(node_args['external_request_id'], manifest['filename'])

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'external_request_id' in node_args

        for manifest in result['manifest']:
            assert 'content' in manifest
            self.store_blob(manifest['content'].encode(), self._construct_object_key(node_args, manifest))

        return "{}:{}".format(self.bucket_name, node_args['external_request_id'])
