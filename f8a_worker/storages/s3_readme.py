"""S3 storage for README files."""

from . import AmazonS3


class S3Readme(AmazonS3):
    """S3 storage for README files."""

    @staticmethod
    def _construct_object_key(**arguments):
        """Construct object key."""
        return "{ecosystem}/{name}/README.json".format(**arguments)

    def retrieve_readme_json(self, ecosystem, name):
        """Retrieve README.json from the storage."""
        object_key = self._construct_object_key(ecosystem=ecosystem, name=name)
        return self.retrieve_dict(object_key)

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Store README.json."""
        assert 'ecosystem' in node_args
        assert 'name' in node_args

        if result is None:
            return

        object_key = self._construct_object_key(**node_args)
        self.store_dict(result, object_key)

        return "{}:{}".format(self.bucket_name, object_key)
