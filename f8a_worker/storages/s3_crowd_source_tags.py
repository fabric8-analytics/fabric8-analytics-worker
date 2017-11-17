#!/usr/bin/env python3

from . import AmazonS3


class S3GitHubManifestMetadata(AmazonS3):

    def _construct_object_key(self, arguments):
        path = self.get_object_key_path(arguments['ecosystem'])
        return "{path}/package_topic.json".format(path=path)

    @staticmethod
    def get_object_key_path(ecosystem):
        return "{ecosystem}".format(ecosystem=ecosystem) + "github/data_input_raw_package_list/"

    def store(self, node_args, flow_name, task_name, task_id, result):
        assert 'ecosystem' in node_args

        object_key = self._construct_object_key(node_args)
        version_id = self.store_dict(result[1], object_key)
        return version_id

    def store_raw_manifest(self, ecosystem, repo_path, filename, manifest):
        path = self.get_object_key_path(ecosystem, repo_path)
        self.store_blob(manifest, "{path}/{filename}".format(path=path, filename=filename))
