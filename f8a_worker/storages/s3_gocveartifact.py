"""S3 storage for repository description."""

from . import AmazonS3


class S3GoCveArtifact(AmazonS3):
    """S3 storage for repository description."""

    @staticmethod
    def _construct_object_key(**arguments):
        """Construct object key."""
        return "{package}/issue.json".format(**arguments)

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Save repository description into the storage."""
        assert 'package' in node_args

        object_key = self._construct_object_key(**node_args)
        self.store_blob(result.encode(), object_key)

        return "{}:{}".format(self.bucket_name, object_key)
