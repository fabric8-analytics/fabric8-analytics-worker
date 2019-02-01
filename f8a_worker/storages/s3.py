#!/usr/bin/env python3

"""Basic interface to the Amazon S3 database."""

import os
import json
import uuid
import boto3
import botocore
from selinon import DataStorage
from selinon import StoragePool
from f8a_worker.defaults import configuration


class AmazonS3(DataStorage):
    """Basic interface to the Amazon S3 database."""

    _DEFAULT_REGION_NAME = 'us-east-1'
    _DEFAULT_BUCKET_NAME = 'bayesian-core-unknown'
    _DEFAULT_LOCAL_ENDPOINT = 'http://coreapi-s3:33000'
    _DEFAULT_ENCRYPTION = 'aws:kms'
    _DEFAULT_VERSIONED = True

    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, bucket_name=None,
                 region_name=None, endpoint_url=None, use_ssl=False, encryption=None,
                 versioned=None):
        """Initialize object, setup connection to the AWS S3."""
        # TODO: reduce cyclomatic complexity
        # Priority for configuration options:
        #   1. environment variables
        #   2. arguments passed to constructor
        #   3. defaults as listed in self._DEFAULT_*
        super().__init__()
        self._s3 = None

        self.region_name = configuration.AWS_S3_REGION or region_name or self._DEFAULT_REGION_NAME
        bucket_name = bucket_name or self._DEFAULT_BUCKET_NAME
        self.bucket_name = bucket_name.format(**os.environ)
        self._aws_access_key_id = configuration.AWS_S3_ACCESS_KEY_ID or aws_access_key_id
        self._aws_secret_access_key = \
            configuration.AWS_S3_SECRET_ACCESS_KEY or aws_secret_access_key

        # let boto3 decide if we don't have local development proper values
        self._endpoint_url = None
        self._use_ssl = True
        # 'encryption' (argument) might be False - means don't encrypt
        self.encryption = self._DEFAULT_ENCRYPTION if encryption is None else encryption
        self.versioned = self._DEFAULT_VERSIONED if versioned is None else versioned

        # if we run locally, make connection properties configurable
        if configuration.is_local_deployment():
            self._endpoint_url = configuration.S3_ENDPOINT_URL or endpoint_url or \
                                 self._DEFAULT_LOCAL_ENDPOINT
            self._use_ssl = use_ssl
            self.encryption = False

        if self._aws_access_key_id is None or self._aws_secret_access_key is None:
            raise ValueError("AWS configuration not provided correctly, "
                             "both key id and key is needed")

    @staticmethod
    def dict2blob(dictionary):
        """Serialize the dictionary into JSON format.

        :param dictionary: dictionary to convert to JSON
        :return: encoded bytes representing pretty-printed JSON
        """
        return json.dumps(dictionary, sort_keys=True, separators=(',', ': '), indent=2).encode()

    def _create_bucket_if_needed(self):
        """Create desired bucket based on configuration if does not exist.

        Versioning is enabled on creation.
        """
        # check that the bucket exists - see boto3 docs
        try:
            self._s3.meta.client.head_bucket(Bucket=self.bucket_name)
        except botocore.exceptions.ClientError as exc:
            # if a client error is thrown, then check that it was a 404 error.
            # if it was a 404 error, then the bucket does not exist.
            try:
                error_code = int(exc.response['Error']['Code'])
            except (TypeError, ValueError, KeyError):
                raise
            if error_code == 404:
                self._create_bucket()
            else:
                raise

    def _create_bucket(self, tagged=True):
        """Create bucket."""
        # Yes boto3, you are doing it right:
        #   https://github.com/boto/boto3/issues/125
        if self.region_name == 'us-east-1':
            self._s3.create_bucket(Bucket=self.bucket_name)
        else:
            self._s3.create_bucket(Bucket=self.bucket_name,
                                   CreateBucketConfiguration={
                                       'LocationConstraint': self.region_name
                                   })
        if self.versioned and not configuration.is_local_deployment():
            # Do not enable versioning when running locally.
            # Our S3 alternatives are not capable to handle it.
            self._s3.BucketVersioning(self.bucket_name).enable()

        bucket_tag = configuration.DEPLOYMENT_PREFIX
        if tagged and bucket_tag and not configuration.is_local_deployment():
            self._s3.BucketTagging(self.bucket_name).put(
                Tagging={
                    'TagSet': [
                        {
                            'Key': 'ENV',
                            'Value': bucket_tag
                        }
                    ]
                }
            )

    def object_exists(self, object_key):
        """Check if the there is an object with the given key in bucket, does only HEAD request."""
        try:
            self._s3.Object(self.bucket_name, object_key).load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                exists = False
            else:
                raise
        else:
            exists = True
        return exists

    def connect(self):
        """Connect to the S3 database."""
        session = boto3.session.Session(aws_access_key_id=self._aws_access_key_id,
                                        aws_secret_access_key=self._aws_secret_access_key,
                                        region_name=self.region_name)
        # signature version is needed to connect to new regions which support only v4
        self._s3 = session.resource('s3', config=botocore.client.Config(signature_version='s3v4'),
                                    use_ssl=self._use_ssl, endpoint_url=self._endpoint_url)
        self._create_bucket_if_needed()

    def is_connected(self):
        """Check if the connection to database has been established."""
        return self._s3 is not None

    def disconnect(self):
        """Close the connection to S3 database."""
        del self._s3
        self._s3 = None

    def retrieve(self, flow_name, task_name, task_id):
        """Retrieve data from the storage. Method needs to be implemented by descendent classes."""
        raise NotImplementedError()

    def store(self, node_args, flow_name, task_name, task_id, result):
        """Save data to the storage. Method that needs to be implemented by descendent classes."""
        raise NotImplementedError()

    @staticmethod
    def _get_fake_version_id():
        """Generate fake S3 object version id."""
        return uuid.uuid4().hex + '-unknown'

    def store_file(self, file_path, object_key):
        """Store file onto S3.

        :param file_path: path to file to be stored
        :param object_key: object key under which the file should be stored
        :return: object version or None if versioning is off
        """
        f = None
        try:
            f = open(file_path, 'rb')
            return self.store_blob(f, object_key)
        finally:
            if f is not None:
                f.close()

    def store_blob(self, blob, object_key):
        """Store blob onto S3.

        :param blob: bytes or stream to be stored
        :param object_key: object key under which the blob should be stored
        :return: object version or None if versioning is off
        """
        self._create_bucket_if_needed()
        put_kwargs = {'Body': blob}
        if self.encryption:
            put_kwargs['ServerSideEncryption'] = self.encryption

        response = self._s3.Object(self.bucket_name, object_key).put(**put_kwargs)

        if 'VersionId' not in response and configuration.is_local_deployment() and self.versioned:
            # If we run local deployment, our local S3 alternative does not
            # support versioning. Return a fake one.
            return self._get_fake_version_id()

        return response.get('VersionId')

    def store_dict(self, dictionary, object_key):
        """Store dictionary as JSON on S3.

        :param dictionary: dictionary to be stored
        :param object_key: object key under which the blob should be stored
        :return: object version or None if versioning is off
        """
        blob = self.dict2blob(dictionary)
        return self.store_blob(blob, object_key)

    def retrieve_file(self, object_key, file_path):
        """Download an S3 object to a file."""
        self._s3.Object(self.bucket_name, object_key).download_file(file_path)

    def retrieve_blob(self, object_key):
        """Retrieve remote object content."""
        return self._s3.Object(self.bucket_name, object_key).get()['Body'].read()

    def retrieve_dict(self, object_key):
        """Retrieve a dictionary stored as JSON from S3."""
        return json.loads(self.retrieve_blob(object_key).decode())

    def retrieve_latest_version_id(self, object_key):
        """Retrieve latest version identifier for the given object.

        :param object_key: key under which the object is stored
        :return: version identifier
        """
        if not self.versioned:
            raise AttributeError("Cannot retrieve version of object '{}': "
                                 "bucket '{}' is not configured to be versioned".
                                 format(object_key, self.bucket_name))

        if configuration.is_local_deployment():
            return self._get_fake_version_id()

        return self._s3.Object(self.bucket_name, object_key).version_id

    @staticmethod
    def is_enabled():
        """:return: True if S3 sync is enabled, False otherwise."""
        try:
            return configuration.BAYESIAN_SYNC_S3
        except ValueError:
            return False

    def store_error(self, node_args, flow_name, task_name, task_id, exc_info):
        """Store error to Postgres/RDS so we know about task failures that store data on S3."""
        if flow_name == 'bayesianAnalysisFlow':
            postgres = StoragePool.get_connected_storage('BayesianPostgres')
        elif flow_name == 'bayesianPackageAnalysisFlow':
            postgres = StoragePool.get_connected_storage('PackagePostgres')
        else:
            raise RuntimeError("Unable to store error, error storing not defined for flow '%s'" %
                               flow_name)

        return postgres.store_error(node_args, flow_name, task_name, task_id, exc_info)
