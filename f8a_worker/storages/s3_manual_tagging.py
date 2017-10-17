from . import AmazonS3


class S3ManualTagging(AmazonS3):
    def store_user_data(self, input_json):
        if input_json.get('user') is None or input_json.get('ecosystem') is None:
            return {'status': 'failure'}
        file_name = self.get_file_name(input_json.get('user'), input_json.get('ecosystem'))
        data = input_json.get('data', {})
        self.store_dict(data, file_name)
        return {'status': 'success'}

    def fetch_user_data(self, user, ecosystem):
        file_name = self.get_file_name(user, ecosystem)
        file_data = self.retrieve_dict(file_name)
        user_json = {
            'user': user,
            'data': file_data
        }
        return user_json

    def get_file_name(self, user, ecosystem):
        postfix = "_user.json"
        file_name = ecosystem + "/" + user + postfix
        return file_name
