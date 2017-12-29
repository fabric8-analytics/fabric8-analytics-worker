from . import AmazonS3


class S3KronosAppend(AmazonS3):

    def store_updated_data(self, input_json, file_name):
        self.store_dict(input_json, file_name)

    def fetch_existing_data(self, file_name):
        file_data = self.retrieve_dict(file_name)
        return file_data
