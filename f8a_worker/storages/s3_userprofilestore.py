"""Import AmazonS3"""
from . import AmazonS3

class S3UserProfileStore(AmazonS3):
    """An Adapter Class to handle storage of User Profile information to S3"""
    def store_in_bucket(self, content):
        """Stores the User Profile information into S3 Buckets"""
        email = content.get('email')
        folder = 'new_user_profile'
        key = folder + '/' + email + '.json'
        self.store_dict(content, key)
