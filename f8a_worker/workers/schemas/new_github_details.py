"""JSL schema for Github worker results."""

import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease, added_in, removed_in
from .github_details import GithubLastYearCommits, GithubUpdatedIssues, GithubUpdatedPullRequests

# Describe v1-0-0
ROLE_v1_0_2 = "v1-0-2"
ROLE_v1_0_3 = "v1-0-3"
ROLE_v1_0_4 = "v1-0-4"
ROLE_v2_0_0 = "v2-0-0"
ROLE_v2_0_1 = "v2-0-1"
ROLE_v2_0_2 = "v2-0-2"


class NewGithubDetail(jsl.Document):
    """JSL schema for Github worker results details."""

    class Options(object):
        """JSL schema for Github worker results details."""

        definition_id = "github_extracted_details"
        description = "Details of Github inspection"

    # we don't mandate any of these fields, because they may not be present
    forks_count = jsl.IntField()
    last_year_commits = jsl.DocumentField(GithubLastYearCommits, as_ref=True)
    open_issues_count = jsl.IntField()
    stargazers_count = jsl.IntField()
    subscribers_count = jsl.IntField()
    latest_version = jsl.StringField()
    with removed_in(ROLE_v2_0_0) as until_v2_0_0:
        until_v2_0_0.updated_issues = jsl.DocumentField(GithubUpdatedIssues, as_ref=True)
        until_v2_0_0.updated_pull_requests = jsl.DocumentField(GithubUpdatedPullRequests,
                                                               as_ref=True)
    with added_in(ROLE_v1_0_2) as since_v1_0_2:
        since_v1_0_2.contributors_count = jsl.IntField()
    with jsl.Scope(ROLE_v1_0_3) as v1_0_3:
        v1_0_3.topics = jsl.ArrayField(jsl.StringField(), required=True)
    with added_in(ROLE_v1_0_4) as since_v1_0_4:
        since_v1_0_4.topics = jsl.ArrayField(jsl.StringField())
    with added_in(ROLE_v2_0_1) as since_v2_0_1:
        since_v2_0_1.license = jsl.DictField()
    with added_in(ROLE_v2_0_2) as since_v2_0_2:
        since_v2_0_2.updated_on = jsl.StringField(required=True)


class NewGithubResult(JSLSchemaBaseWithRelease):
    """JSL schema for Github worker results."""

    class Options(object):
        """JSL schema for Github worker results."""

        definition_id = "new_github_details"
        description = "Result of Github worker"

    status = jsl.StringField(enum=["success", "error", "unknown"], required=True)
    details = jsl.DocumentField(NewGithubDetail, required=True, as_ref=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = NewGithubResult
