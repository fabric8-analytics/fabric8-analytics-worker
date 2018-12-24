"""S3 storage for repository description."""

from . import AmazonS3
import logging

logger = logging.getLogger(__name__)


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