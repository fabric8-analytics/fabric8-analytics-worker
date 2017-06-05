#!/usr/bin/env python3

from . import AmazonS3


class S3GitHubManifestMetadata(AmazonS3):

    def _construct_object_key(self, arguments, result_name='metadata'):
        path = self._get_object_key_path(arguments['ecosystem'], arguments['repo_name'])
        return "{path}/{name}.json".format(path=path, name=result_name)

    @staticmethod
    def _get_object_key_path(ecosystem, repo_name):
        return "{ecosystem}/{repo_name}".format(ecosystem=ecosystem, repo_name=repo_name.replace('/', ':'))

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args
        assert 'repo_name' in node_args

        object_key = self._construct_object_key(node_args, result_name=result[0])
        version_id = self.store_dict(result[1], object_key)
        return version_id

    def store_raw_manifest(self, ecosystem, repo_path, filename, manifest):
        path = self._get_object_key_path(ecosystem, repo_path)
        self.store_blob(manifest, "{path}/{filename}".format(path=path, filename=filename))
