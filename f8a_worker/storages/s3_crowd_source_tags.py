"""S3 storage for crowd-source tags."""

from . import AmazonS3


class S3CrowdSourceTags(AmazonS3):
    """S3 storage for crowd-source tags."""

    @staticmethod
    def get_object_key_path(ecosystem):
        """Construct object key path."""
        return "{ecosystem}/github/data_input_raw_package_list/".format(ecosystem=ecosystem)

    def retrieve_package_topic(self, ecosystem):
        """Retrieve package_topic.json from the storage."""
        path = self.get_object_key_path(ecosystem)
        object_key = "{path}/package_topic.json".format(path=path)
        return self.retrieve_dict(object_key)

    def store_package_topic(self, ecosystem, results):
        """Store crowd_sourcing_package_topic.json."""
        path = self.get_object_key_path(ecosystem)
        object_key = "{path}/crowd_sourcing_package_topic.json".format(path=path)
        self.store_dict(results, object_key)
