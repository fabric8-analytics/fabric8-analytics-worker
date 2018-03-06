"""S3 storage for repository description."""

from . import AmazonS3


class S3RepositoryDescription(AmazonS3):
    """S3 storage for repository description."""

    @staticmethod
    def _construct_object_key(**arguments):
        """Construct object key."""
        return "{ecosystem}/{name}.txt".format(**arguments)

    def retrieve_repository_description(self, ecosystem, name):
        """Retrieve repository description."""
        object_key = self._construct_object_key(ecosystem=ecosystem, name=name)
        return self.retrieve_blob(object_key).decode()

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Store."""
        assert 'ecosystem' in node_args
        assert 'name' in node_args

        object_key = self._construct_object_key(**node_args)
        self.store_blob(result.encode(), object_key)

        return "{}:{}".format(self.bucket_name, object_key)
