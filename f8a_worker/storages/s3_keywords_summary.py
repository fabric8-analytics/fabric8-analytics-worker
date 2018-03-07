"""S3 storage for keywords summary."""

from . import AmazonS3


class S3KeywordsSummary(AmazonS3):
    """S3 storage for keywords summary."""

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Store the result into the AWS S3."""
        object_key = "{ecosystem}/{name}.json".format(**node_args)
        return self.store_dict(result, object_key)
