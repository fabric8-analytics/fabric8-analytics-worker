#!/usr/bin/env python

"""Import all storages."""

from .postgres import BayesianPostgres
from .package_postgres import PackagePostgres
from .s3 import AmazonS3
from .s3_artifacts import S3Artifacts
from .s3_temp_artifacts import S3TempArtifacts
from .s3_data import S3Data
from .s3_package_data import S3PackageData
from .s3_manifests import S3Manifests
from .s3_mavenindex import S3MavenIndex
from .s3_readme import S3Readme
from .s3_gh_manifests import S3GitHubManifestMetadata
from .s3_userprofilestore import S3UserProfileStore
from .s3_description_repository import S3RepositoryDescription
from .s3_userintent import S3UserIntent
from .s3_manual_tagging import S3ManualTagging
from .s3_crowd_source_tags import S3CrowdSourceTags

# avoid Vulture and Pyflakes warnings
assert BayesianPostgres is not None
assert PackagePostgres is not None
assert AmazonS3 is not None
assert S3Artifacts is not None
assert S3TempArtifacts is not None
assert S3Data is not None
assert S3PackageData is not None
assert S3Manifests is not None
assert S3MavenIndex is not None
assert S3Readme is not None
assert S3GitHubManifestMetadata is not None
assert S3UserProfileStore is not None
assert S3RepositoryDescription is not None
assert S3UserIntent is not None
assert S3ManualTagging is not None
assert S3CrowdSourceTags is not None
