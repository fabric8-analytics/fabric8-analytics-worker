#!/usr/bin/env python3

import os
import json
import uuid
import boto3
import botocore
from selinon import DataStorage
from cucoslib.utils import json_serial


class AmazonS3(DataStorage):
    _DEFAULT_REGION_NAME = 'us-east-1'
    _DEFAULT_BUCKET_NAME = 'bayesian-core-data'
    _DEFAULT_LOCAL_ENDPOINT = 'http://coreapi-s3:33000'
    _DEFAULT_ENCRYPTION = 'aws:kms'

    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None, bucket_name=None,
                 region_name=None, endpoint_url=None, use_ssl=False, encryption=None):
        # Priority for configuration options:
        #   1. environment variables
        #   2. arguments passed to constructor
        #   3. defaults as listed in self._DEFAULT_*
        super().__init__()
        self._s3 = None

        self._region_name = os.environ.get('AWS_S3_REGION', region_name) or self._DEFAULT_REGION_NAME
        self._bucket_name = os.environ.get('AWS_S3_BUCKET_NAME', bucket_name) or self._DEFAULT_BUCKET_NAME
        self._bucket_name = self._bucket_name.format(**os.environ)
        self._aws_access_key_id = os.environ.get('AWS_S3_ACCESS_KEY_ID', aws_access_key_id)
        self._aws_secret_access_key = os.environ.get('AWS_S3_SECRET_ACCESS_KEY', aws_secret_access_key)

        # let boto3 decide if we don't have local development proper values
        self._endpoint_url = None
        self._use_ssl = True
        # 'encryption' (argument) might be False - means don't encrypt
        self._encryption = self._DEFAULT_ENCRYPTION if encryption is None else encryption

        # if we run locally, make connection properties configurable
        if self._is_local_deployment():
            self._endpoint_url = endpoint_url or self._DEFAULT_LOCAL_ENDPOINT
            self._use_ssl = use_ssl
            self._encryption = False

        if self._aws_access_key_id is None or self._aws_secret_access_key is None:
            raise ValueError("AWS configuration not provided correctly, both key id and key is needed")

    @staticmethod
    def _is_local_deployment():
        """
        :return: True if this storage does not store data directly in AWS S3 but in some fake S3 instead
        """
        aws_access_key_id_provided = os.environ.get('AWS_S3_ACCESS_KEY_ID') is not None
        aws_secret_access_key_provided = os.environ.get('AWS_S3_SECRET_ACCESS_KEY') is not None

        if aws_access_key_id_provided != aws_secret_access_key_provided:
            raise ValueError("Misleading configuration, you have to provide both 'AWS_S3_ACCESS_KEY_ID' "
                             "and 'AWS_S3_SECRET_ACCESS_KEY' for connection to AWS")

        if "AWS_ACCESS_KEY_ID" in os.environ:
            raise RuntimeError("Do not use AWS_ACCESS_KEY_ID in order to access S3, use 'AWS_S3_ACCESS_KEY_ID'")

        if "AWS_SECRET_ACCESS_KEY" in os.environ:
            raise RuntimeError("Do not use AWS_SECRET_ACCESS_KEY in order to access S3, use 'AWS_S3_SECRET_ACCESS_KEY'")

        return not (aws_access_key_id_provided or aws_secret_access_key_provided)

    @staticmethod
    def dict2blob(dictionary):
        """
        :param dictionary: dictionary to convert to JSON
        :return: encoded bytes representing pretty-printed JSON
        """
        return json.dumps(dictionary, sort_keys=True, separators=(',', ': '), indent=2).encode()

    def _create_bucket_if_needed(self, bucket_name, versioned=True):
        """
        Create desired bucket based on configuration if does not exist. Versioning is enabled on creation.
        """
        # check that the bucket exists - see boto3 docs
        try:
            self._s3.meta.client.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as exc:
            # if a client error is thrown, then check that it was a 404 error.
            # if it was a 404 error, then the bucket does not exist.
            try:
                error_code = int(exc.response['Error']['Code'])
            except:
                raise
            if error_code == 404:
                self._create_bucket(bucket_name, region_name=self._region_name, versioned=versioned)
            else:
                raise

    def _create_bucket(self, bucket_name, region_name=_DEFAULT_REGION_NAME, versioned=True, tagged=True):
        # Yes boto3, you are doing it right:
        #   https://github.com/boto/boto3/issues/125
        if region_name == 'us-east-1':
            self._s3.create_bucket(Bucket=bucket_name)
        else:
            self._s3.create_bucket(Bucket=bucket_name,
                                   CreateBucketConfiguration={
                                       'LocationConstraint': region_name
                                   })
        if versioned and not self._is_local_deployment():
            # Do not enable versioning when running locally. Our S3 alternatives are not capable to handle it.
            self._s3.BucketVersioning(bucket_name).enable()

        bucket_tag = os.environ.get('DEPLOYMENT_PREFIX')
        if tagged and bucket_tag and not self._is_local_deployment():
            self._s3.BucketTagging(bucket_name).put(
                Tagging={
                    'TagSet': [
                        {
                            'Key': 'ENV',
                            'Value': bucket_tag
                        }
                    ]
                }
            )

    @staticmethod
    def _construct_base_file_name(ecosystem, name, version):
        """Construct location of EPV in the bucket"""
        return "{ecosystem}/{name}/{version}".format(ecosystem=ecosystem, name=name, version=version)

    @staticmethod
    def _base_file_content(old_file_content, result):
        analyses_list = list(set(old_file_content.get('analyses', [])) | set(result.get('analyses', {}).keys()))

        content = result
        content['analyses'] = analyses_list
        if 'finished_at' in content:
            content['finished_at'] = json_serial(content['finished_at'])
        if 'started_at' in content:
            content['started_at'] = json_serial(content['started_at'])

        return content

    def object_exists(self, bucket_name, object_key):
        """Check if the there is an object with the given key in bucket, does only HEAD request"""
        try:
            self._s3.Object(bucket_name, object_key).load()
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                exists = False
            else:
                raise
        else:
            exists = True
        return exists

    def _add_base_file_record(self, base_name, result):
        """Add info about analyses available for the given EPV"""
        base_file_name = base_name + '.json'

        # remove entries we don't want to keep
        result.pop('access_count', None)

        try:
            file_content = self.retrieve_blob(self._bucket_name, base_file_name)
            # if we have file that is empty, let's overwrite it
            file_content = json.loads(file_content.decode() or '{}')
        except botocore.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] == 'NoSuchKey':
                # we are inserting for the first time, assign whole content
                file_content = {}
            else:
                # Some another error, not no such file
                raise

        # we keep track only of tasks that were run, so keep only keys
        file_content = self._base_file_content(file_content, result)
        self.store_blob(blob=self.dict2blob(file_content), object_key=base_file_name,
                        bucket_name=self._bucket_name, versioned=True, encrypted=True)

    def connect(self):
        session = boto3.session.Session(aws_access_key_id=self._aws_access_key_id,
                                        aws_secret_access_key=self._aws_secret_access_key,
                                        region_name=self._region_name)
        # signature version is needed to connect to new regions which support only v4
        self._s3 = session.resource('s3', config=botocore.client.Config(signature_version='s3v4'),
                                    use_ssl=self._use_ssl, endpoint_url=self._endpoint_url)
        self._create_bucket_if_needed(self._bucket_name, versioned=True)

    def is_connected(self):
        return self._s3 is not None

    def disconnect(self):
        del self._s3
        self._s3 = None

    def retrieve(self, flow_name, task_name, task_id):
        raise NotImplementedError()

    @staticmethod
    def _get_fake_version_id():
        return uuid.uuid4().hex + '-unknown'

    def store(self, node_args, flow_name, task_name, task_id, result):
        # For the given EPV, the path to task result is:
        #
        #   <ecosystem>/<package_name>/<version>/<task_name>.json
        #
        # There is also a top level JSON file located at:
        #
        #   <ecosystem>/<package_name>/<version>.json
        #
        # that stores JSON in where tasks are available under 'tasks' key:
        #
        #  {'tasks': [ 'digests', 'metadata', ...]}
        #
        assert 'ecosystem' in node_args
        assert 'name' in node_args
        assert 'version' in node_args

        # we don't want args propagated from init
        result.get('analyses', {}).pop('InitAnalysisFlow', None)

        base_file_name = self._construct_base_file_name(node_args['ecosystem'],
                                                        node_args['name'],
                                                        node_args['version'])

        for task_name, task_result in result.get('analyses', {}).items():
            file_name = "{base_file_name}/{task_name}.json".format(base_file_name=base_file_name,
                                                                   task_name=task_name)
            self.store_blob(blob=self.dict2blob(task_result), object_key=file_name,
                            bucket_name=self._bucket_name, versioned=True, encrypted=True)

        self._add_base_file_record(base_file_name, result)
        return "{}:{}".format(self._bucket_name, base_file_name)

    def store_file(self, file_path, object_key, bucket_name, versioned=False, encrypted=True):
        """Store file determined by the `file_path` to S3."""
        with open(file_path, 'rb') as f:
            self.store_blob(f.read(), object_key, bucket_name, versioned, encrypted)

    def store_blob(self, blob, object_key, bucket_name, versioned=False, encrypted=True):
        self._create_bucket_if_needed(bucket_name, versioned)
        put_kwargs = {'Body': blob}
        if encrypted and self._encryption:
            put_kwargs['ServerSideEncryption'] = self._encryption
        self._s3.Object(bucket_name, object_key).put(**put_kwargs)

    def store_dict(self, dictionary, object_key, bucket_name, versioned=False, encrypted=True):
        """ Store dictionary as JSON on S3 """
        blob = self.dict2blob(dictionary)
        self.store_blob(blob, object_key, bucket_name, versioned, encrypted)

    def retrieve_file(self, bucket_name, object_key, file_path):
        """ Download an S3 object to a file. """
        self._s3.Object(bucket_name, object_key).download_file(file_path)

    def retrieve_blob(self, bucket_name, object_key):
        """ Retrieve remote object content. """
        return self._s3.Object(bucket_name, object_key).get()['Body'].read()

    def retrieve_dict(self, bucket_name, object_key):
        """ Retrieve a dictionary stored as JSON from S3 """
        return json.loads(self.retrieve_blob(bucket_name, object_key).decode())

    @staticmethod
    def is_enabled():
        """:return: True if S3 sync is enabled, False otherwise."""
        try:
            return int(os.environ.get('BAYESIAN_SYNC_S3', 0)) == 1
        except ValueError:
            return False
