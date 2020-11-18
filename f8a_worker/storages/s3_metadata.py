"""S3 storage for Github details files."""

from . import AmazonS3


class S3MetaData(AmazonS3):
    """S3 storage for Github details files."""

    @staticmethod
    def _construct_object_key(**arguments):
        """Construct object key."""
        return "{ecosystem}/{name}/{version}/metadata.json".format(**arguments)

    def store_data(self, node_args, result):
        """Store github details as a json."""
        assert 'ecosystem' in node_args
        assert 'name' in node_args

        if result is None:
            return

        object_key = self._construct_object_key(**node_args)
        self.store_dict(result, object_key)

        return "{}:{}".format(self.bucket_name, object_key)
