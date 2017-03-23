import jsl

from cucoslib.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Dependency snapshot v1-0-0"
})

class Dependency(jsl.Document):
    class Options(object):
        definition_id = 'dependency_object'
        description = 'Dependency Object'

    ecosystem = jsl.StringField(required=True)
    name = jsl.StringField(required=True)
    version = jsl.OneOfField([jsl.StringField(), jsl.NullField()], required=True)
    declaration = jsl.StringField(required=True)
    resolved_at = jsl.StringField(required=True)


class DependencySnapshotDetail(jsl.Document):
    class Options(object):
        definition_id = 'dependency_snapshot_detail'
        description = 'Details of Dependency Snapshot run on a component'

    runtime = jsl.ArrayField(jsl.DocumentField(Dependency, as_ref=True))


class DependenciesCounts(jsl.Document):
    class Options(object):
        definition_id = 'dependencies_counts'
        description = 'Counts of various types of dependencies'

    runtime = jsl.IntField()


class DependencySnapshotSummary(jsl.Document):
    class Options(object):
        definition_id = 'dependency_snapshot_summary'
        description = 'Summary of Dependency Snapshot run on a component'

    errors = jsl.ArrayField(jsl.StringField(), required=True)
    dependency_counts = jsl.DocumentField(DependenciesCounts, as_ref=True, required=True)


class DependencySnapshotResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = 'dependency_snapshot'
        description = 'Result of Dependency Snapshot worker'

    status = jsl.StringField(enum=['success', 'error'], required=True)
    details = jsl.DocumentField(DependencySnapshotDetail, as_ref=True, required=True)
    summary = jsl.DocumentField(DependencySnapshotSummary, as_ref=True, required=True)


THE_SCHEMA = DependencySnapshotResult
