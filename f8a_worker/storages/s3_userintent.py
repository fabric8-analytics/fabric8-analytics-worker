#!/usr/bin/env python3

from . import AmazonS3

class S3UserIntent(AmazonS3):
    def store_in_bucket(self, input_json):
        key = "{}".format(input_json["component"])
        if self.object_exists(key):
            existing_object = self.retrieve_dict(key)
            existing_intent_list = existing_object.get('intent', [])
            input_json.get('intent', []).extend(existing_intent_list)
        self.store_dict(input_json, key)
