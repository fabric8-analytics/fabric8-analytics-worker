"""S3 storage for repository description."""

from . import AmazonS3
import logging

logger = logging.getLogger(__name__)


class S3IssuesPRs(AmazonS3):
    """S3 storage for repository description."""

    @property
    def bucket_name(self):
        """Get bucket name."""
        return self._bucket_name

    @bucket_name.setter
    def bucket_name(self, bucket_name):
        """Set bucket name, but make it all lower case."""
        # Since March 1, 2018, Amazon S3 no longer supports creating bucket names
        # that contain uppercase letters or underscores.
        # Docs: https://docs.aws.amazon.com/AmazonS3/latest/dev/BucketRestrictions.html
        # TODO: remove once deployment prefix in staging (STAGE-) is fixed and data is migrated
        self._bucket_name = bucket_name.lower()

    @staticmethod
    def _construct_object_key(**arguments):
        """Construct object key."""
        return "{package}/issue.json".format(**arguments)

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Save repository description into the storage."""
        assert 'package' in node_args

        object_key = self._construct_object_key(**node_args)
        self.store_dict(result, object_key)

        return "{}:{}".format(self.bucket_name, object_key)

    def retrieve(self, flow_name, task_name, task_id):
        """Retrieve the results.

        Not implemented for this adapter.

        """
        return None

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info, result=None):
        """Postgres storage not required."""
        logger.error('{task_name} failed: id={task_id} args={args}'.format(
            task_name=task_name, task_id=task_id, args=node_args)
        )
