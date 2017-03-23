import os
from selinon import StoragePool
from cucoslib.base import BaseTask


class ManifestKeeperTask(BaseTask):
    description = 'Keep manifest stored on S3'
    _RAW_BUCKET_NAME = '{DEPLOYMENT_PREFIX}-bayesian-core-manifests'
    _OBJECT_KEY = 'manifest.json'

    @property
    def _bucket_name(self):
        return self._RAW_BUCKET_NAME.format(**os.environ)

    def _construct_object_key(self, arguments, manifest):
        self._strict_assert(manifest.get('filename'))
        return "{}/{}".format(arguments['external_request_id'], manifest['filename'])

    def execute(self, arguments):
        self._strict_assert(arguments.get('manifest'))
        self._strict_assert(arguments.get('external_request_id'))

        s3 = StoragePool.get_connected_storage('AmazonS3')

        for manifest in arguments['manifest']:
            s3.store_blob(
                manifest['content'].encode(),
                object_key=self._construct_object_key(arguments, manifest),
                bucket_name=self._bucket_name,
                versioned=False,
                encrypted=True
            )
