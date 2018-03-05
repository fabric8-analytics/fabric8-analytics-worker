#!/usr/bin/env python3

"""S3 storage for temporary content."""

from . import AmazonS3
from f8a_worker.defaults import F8AConfiguration


class S3TempArtifacts(AmazonS3):
    """S3 storage for temporary content.

    All objects in the backing bucket will expire in 31 days,
    if not configured otherwise.
    """

    default_expiration_rule = {
        'Rules': [
            {
                'ID': 'expire-rule',
                'Expiration': {
                    'Days': 31
                },
                'Filter': {'Prefix': ''},
                'Status': 'Enabled'
            }
        ]
    }

    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, bucket_name=None,
                 region_name=None, endpoint_url=None, use_ssl=False, encryption=None,
                 versioned=None, days_to_expire=None):
        """Initialize object."""
        super().__init__(aws_access_key_id=aws_access_key_id,
                         aws_secret_access_key=aws_secret_access_key,
                         bucket_name=bucket_name, region_name=region_name,
                         endpoint_url=endpoint_url, use_ssl=use_ssl,
                         encryption=encryption, versioned=versioned)

        days = int(days_to_expire)
        if days:
            self.default_expiration_rule['Rules'][0]['Expiration']['Days'] = days

    def _create_bucket(self, tagged=True):
        """Create bucket with lifecycle management."""
        super()._create_bucket(tagged=tagged)

        # minio doesn't support lifecycle management
        if not F8AConfiguration.is_local_deployment():
            self._s3.meta.client.put_bucket_lifecycle_configuration(
                Bucket=self.bucket_name,
                LifecycleConfiguration=self.default_expiration_rule)
