#!/usr/bin/env python3

import json
import botocore
from cucoslib.utils import json_serial
from . import AmazonS3


class S3Data(AmazonS3):
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

    def _add_base_file_record(self, base_name, result):
        """Add info about analyses available for the given EPV"""
        base_file_name = base_name + '.json'

        # remove entries we don't want to keep
        result.pop('access_count', None)

        try:
            file_content = self.retrieve_blob(base_file_name)
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
        self.store_dict(file_content, base_file_name)

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
            object_key = "{base_file_name}/{task_name}.json".format(base_file_name=base_file_name,
                                                                    task_name=task_name)
            # use the custom JSON serializer as we store datetimes to postgres that are not serializable by json
            self.store_dict(task_result, object_key)

        self._add_base_file_record(base_file_name, result)
        return "{}:{}".format(self.bucket_name, base_file_name)
