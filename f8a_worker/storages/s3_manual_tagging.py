from . import AmazonS3


class S3ManualTagging(AmazonS3):
    def store_user_data(self, input_json):
        file_name = self.get_file_name(input_json.get('user'))
        data = input_json.get('data', {})
        ecosystem = data.get('ecosystem', None)
        file_name = ecosystem + "/" + file_name
        self.store_dict(data, file_name)

    def fetch_user_data(self, user, ecosystem):
        user_json = {}
        file_name = self.get_file_name(user)
        file_name = ecosystem + "/" + file_name
        file_data = self.retrieve_dict(file_name)
        user_json['user'] = input_json['user']
        user_json['data'] = file_data
        return user_json

    def get_file_name(self, user):
        postfix = "_user.json"
        file_name = user + postfix
        return file_name
