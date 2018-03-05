"""S3 storage for manual tagging."""

from . import AmazonS3


class S3ManualTagging(AmazonS3):
    """S3 storage for manual tagging."""

    def store_user_data(self, input_json):
        """Store supplied JSON."""
        if 'user' not in input_json or 'data' not in input_json:
            raise ValueError("User and data are needed in supplied JSON, got "
                             "{} instead".format(input_json))
        file_name = self.get_file_name(input_json.get('user'),
                                       input_json.get('data').get('ecosystem'))
        data = input_json.get('data', {})
        self.store_dict(data, file_name)

    def fetch_user_data(self, user, ecosystem):
        """Fetch user data."""
        file_name = self.get_file_name(user, ecosystem)
        file_data = self.retrieve_dict(file_name)
        user_json = {
            'user': user,
            'data': file_data
        }
        return user_json

    @staticmethod
    def get_file_name(user, ecosystem):
        """Construct file name."""
        postfix = "_user.json"
        file_name = ecosystem + "/" + user + postfix
        return file_name
