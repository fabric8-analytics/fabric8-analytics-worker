#!/usr/bin/env python3

"""Use S3 for manifests."""

from . import AmazonS3


class S3Manifests(AmazonS3):
    """Use S3 for manifests."""

    @staticmethod
    def _construct_object_key(node_args, manifest):
        """Construct object key path."""
        assert 'filename' in manifest
        return "{}/{}".format(node_args['external_request_id'], manifest['filename'])

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Store manifests from result."""
        assert 'external_request_id' in node_args

        for manifest in result['manifest']:
            assert 'content' in manifest
            self.store_blob(manifest['content'].encode(),
                            self._construct_object_key(node_args, manifest))

        return "{}:{}".format(self.bucket_name, node_args['external_request_id'])
