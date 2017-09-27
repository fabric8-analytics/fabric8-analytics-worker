import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease, added_in, removed_in

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_v1_0_1 = "v1-0-1"
ROLE_v1_0_2 = "v1-0-2"
ROLE_v1_0_3 = "v1-0-3"
ROLE_v1_0_4 = "v1-0-4"
ROLE_v2_0_0 = "v2-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Github Results v1-0-0",
    ROLE_v1_0_1: "Github Results v1-0-1",
    ROLE_v1_0_3: "Github Results v1-0-3",
    ROLE_v1_0_4: "Github Results v1-0-4",
    ROLE_v2_0_0: "Github Results v2-0-0",
})


class GithubLastYearCommits(jsl.Document):
    class Options(object):
        definition_id = "github_last_year_commits_details"
        description = "Details of last year Github commits"

    sum = jsl.IntField(required=True)
    weekly = jsl.ArrayField(jsl.IntField(), required=True)


class GithubItemsByTime(jsl.Document):
    class Options(object):
        definition_id = "github_issue&prs_with_time_duration"
        description = "Details of Github issues + prs yearly or monthly or any given date-range"

    opened = jsl.IntField(required=True)
    closed = jsl.IntField(required=True)


class GithubUpdatedIssues(jsl.Document):
    class Options(object):
        definition_id = "github_issues_details"
        description = "Details of updated Github issues"
    with jsl.Scope(ROLE_v1_0_0) as v1_0_0:
        v1_0_0.open = jsl.IntField(required=True)
        v1_0_0.closed = jsl.IntField(required=True)
    with added_in(ROLE_v1_0_1) as since_v1_0_1:
        since_v1_0_1.year = jsl.DocumentField(GithubItemsByTime, as_ref=True)
        since_v1_0_1.month = jsl.DocumentField(GithubItemsByTime, as_ref=True)


class GithubUpdatedPullRequests(GithubUpdatedIssues):
    class Options(object):
        definition_id = "github_pull_requests_details"
        description = "Details of updated Github pull requests"
    with jsl.Scope(ROLE_v1_0_0) as v1_0_0:
        v1_0_0.open = jsl.IntField(required=True)
        v1_0_0.closed = jsl.IntField(required=True)
    with added_in(ROLE_v1_0_1) as since_v1_0_1:
        since_v1_0_1.year = jsl.DocumentField(GithubItemsByTime, as_ref=True)
        since_v1_0_1.month = jsl.DocumentField(GithubItemsByTime, as_ref=True)


class GithubDetail(jsl.Document):
    class Options(object):
        definition_id = "github_extracted_details"
        description = "Details of Github inspection"

    # we don't mandate any of these fields, because they may not be present
    forks_count = jsl.IntField()
    last_year_commits = jsl.DocumentField(GithubLastYearCommits, as_ref=True)
    open_issues_count = jsl.IntField()
    stargazers_count = jsl.IntField()
    subscribers_count = jsl.IntField()
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


class GithubResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "github_details"
        description = "Result of Github worker"

    status = jsl.StringField(enum=["success", "error", "unknown"], required=True)
    details = jsl.DocumentField(GithubDetail, required=True, as_ref=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = GithubResult
