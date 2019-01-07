"""Test f8a_worker.storages.s3_gocveartifact.py."""

from f8a_worker.storages.s3_gocveartifact import S3IssuesPRs


def test_bucket_name():
    """Test that bucket name is all in lower case."""
    storage = S3IssuesPRs(
        aws_access_key_id='x', aws_secret_access_key='y', bucket_name='STAGE-abc'
    )
    assert storage.bucket_name == 'stage-abc'
