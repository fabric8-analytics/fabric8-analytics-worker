import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

ROLE_v2_0_0 = "v2-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v2_0_0: "Libraries.io v2-0-0",
})


class DependentRepositories(jsl.Document):
    class Options(object):
        definition_id = "libraries_io_dependent_repositories"

    count = jsl.IntField(required=True)


class Dependents(jsl.Document):
    class Options(object):
        definition_id = "libraries_io_dependents"

    count = jsl.IntField(required=True)


class RecentRelease(jsl.Document):
    class Options(object):
        definition_id = "libraries_io_releases_recent"

    number = jsl.StringField(required=True)
    published_at = jsl.StringField(required=True)


class Releases(jsl.Document):
    class Options(object):
        definition_id = "libraries_io_releases"

    count = jsl.IntField(required=True)
    recent = jsl.ArrayField(jsl.DocumentField(RecentRelease, as_ref=True))


class LibrariesIoDetails(jsl.Document):
    class Options(object):
        definition_id = "libraries_io_details"

    dependent_repositories = jsl.DocumentField(DependentRepositories, as_ref=True)
    dependents = jsl.DocumentField(Dependents, as_ref=True)
    releases = jsl.DocumentField(Releases, as_ref=True)


class LibrariesIoResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "libraries_io"
        description = "Result of LibrariesIoTask"

    details = jsl.DocumentField(LibrariesIoDetails, as_ref=True, required=True)
    status = jsl.StringField(enum=["success", "error", "unknown"], required=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = LibrariesIoResult
