from . import AmazonS3


class S3UserIntent(AmazonS3):
    def store_in_bucket(self, input_json):
        key = "{}".format(input_json["component"])
        if self.object_exists(key):
            existing_object = self.retrieve_dict(key)
            existing_intent_list = existing_object.get('intent', [])
            input_json.get('intent', []).extend(existing_intent_list)
        self.store_dict(input_json, key)

    def store_master_tags(self, input_json):
        if 'ecosystem' not in input_json or 'data' not in input_json:
            raise ValueError("Ecosystem and data are needed in supplied JSON, got "
                             "{} instead".format(input_json))
        self.store_dict(input_json['data'], input_json['ecosystem'] + '/manual_tag_list.json')

    def fetch_master_tags(self, ecosystem):
        if not ecosystem:
            raise ValueError("Ecosystem is needed to fetch the master tag list")
        file_name = ecosystem + '/master_tag_list.json'
        file_data = self.retrieve_dict(file_name)
        return file_data
