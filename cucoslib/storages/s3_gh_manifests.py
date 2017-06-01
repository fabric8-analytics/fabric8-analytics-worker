#!/usr/bin/env python3

from . import AmazonS3


class S3GitHubManifestMetadata(AmazonS3):
    @staticmethod
    def _construct_object_key(arguments, result_name='metadata'):
        return "{ecosystem}/{repo_name}/{name}.json".format(ecosystem=arguments['ecosystem'],
                                                            repo_name=arguments['repo_name'].replace('/', ':'),
                                                            name=result_name)

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args
        assert 'repo_name' in node_args

        object_key = self._construct_object_key(node_args, result_name=result[0])
        version_id = self.store_dict(result[1], object_key)
        return version_id
