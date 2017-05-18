# TODO: mercator is very different than other workers - do we want to change that?
import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease, added_in

ROLE_v1_0_0 = "v1-0-0"
ROLE_v1_0_1 = "v1-0-1"
ROLE_v1_1_0 = "v1-1-0"
ROLE_v2_0_0 = "v2-0-0"
ROLE_v2_1_0 = "v2-1-0"
ROLE_v2_1_1 = "v2-1-1"
ROLE_v3_0_0 = "v3-0-0"
ROLE_v3_0_1 = "v3-0-1"
ROLE_v3_1_0 = "v3-1-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Package Metadata v1-0-0",
    ROLE_v1_0_1: "Package Metadata v1-0-1",
    ROLE_v1_1_0: "Package Metadata v1-1-0",
    ROLE_v2_0_0: "Package Metadata v2-0-0",
    ROLE_v2_1_0: "Package Metadata v2-1-0",
    ROLE_v2_1_1: "Package Metadata v2-1-1",
    # switching to mercator-go
    ROLE_v3_0_0: "Package Metadata v3-0-0",
    # Make code repository type field optional
    ROLE_v3_0_1: "Package Metadata v3-0-1",
    # Add 'status' and 'summary'
    ROLE_v3_1_0: "Package Metadata v3-1-0",
})

_type_field_required = jsl.Var(
    [(lambda r: r >= ROLE_v3_0_1, False)],
    default=True
)


class CodeRepository(jsl.Document):
    class Options(object):
        definition_id = "metadata_code_repository"
        description = "Code repository description"

    type = jsl.StringField(required=_type_field_required)
    url = jsl.StringField(required=True)


class Maintainer(jsl.Document):
    class Options(object):
        definition_id = "metadata_maintainer"
        description = "Maintainer description"

    name = jsl.StringField()
    email = jsl.StringField()
    url = jsl.StringField()


class LockedDependency(jsl.Document):
    class Options(object):
        definition_id = "metadata_locked_dependency"
        description = "Locked dependency description"

    name = jsl.StringField()
    version = jsl.StringField()
    specification = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    resolved = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    dependencies = jsl.ArrayField(jsl.DocumentField(jsl.RECURSIVE_REFERENCE_CONSTANT, as_ref=True))


class LockFile(jsl.Document):
    class Options(object):
        definition_id = "metadata_lockfile"
        description = "Dependency lock file description"

    runtime = jsl.StringField()
    version = jsl.StringField()
    dependencies = jsl.ArrayField(jsl.DocumentField(LockedDependency, as_ref=True))
    with jsl.Scope(lambda v: v >= ROLE_v3_0_0) as since_v3_0_0:
        since_v3_0_0.name = jsl.StringField()


class NpmShrinkwrap(jsl.Document):
    class Options(object):
        definition_id = "npm_shrinkwrap"
        description = "npm-shrinkwrap description"

    name = jsl.StringField()
    version = jsl.StringField()
    npm_shrinkwrap_version = jsl.StringField()
    node_version = jsl.StringField()
    with jsl.Scope(lambda v: v in (ROLE_v1_0_1, ROLE_v1_1_0)) as v1_0_1_v1_1_0:
        v1_0_1_v1_1_0.resolved_dependencies = jsl.ArrayField(jsl.StringField())
    with jsl.Scope(lambda v: v >= ROLE_v2_0_0) as since_v2_0_0:
        since_v2_0_0.dependencies = jsl.ArrayField(jsl.StringField())
        since_v2_0_0._system = jsl.StringField()


class MetadataDict(jsl.Document):
    class Options(object):
        definition_id = "details_metadata"
        description = "generic metadata dict in details list"

    # some of these may be missing in some ecosystem, so no required=True
    author = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    bug_reporting = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    code_repository = jsl.OneOfField(
        [jsl.DocumentField(CodeRepository, as_ref=True), jsl.NullField()]
    )
    declared_license = jsl.OneOfField(
        [jsl.StringField(), jsl.NullField()]
    )
    dependencies = jsl.OneOfField(
        [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
    )
    description = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    devel_dependencies = jsl.OneOfField(
        [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
    )
    # engines are NPM thingie and can contain lots of various keys
    # so we just allow pretty much anything in that dict
    engines = jsl.OneOfField(
        [jsl.DictField(additional_properties=True), jsl.NullField()]
    )
    files = jsl.OneOfField(
        [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
    )
    git_head = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    homepage = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    keywords = jsl.OneOfField(
        [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
    )

    # metadata is a rubygems thing and can contain arbitrary key/value pairs
    metadata = jsl.OneOfField(
        [jsl.DictField(additional_properties=True), jsl.NullField()]
    )
    name = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    platform = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    readme = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    scripts = jsl.OneOfField(
        [jsl.DictField(additional_properties=True), jsl.NullField()]
    )
    version = jsl.OneOfField([jsl.StringField(), jsl.NullField()])

    with jsl.Scope(lambda v: v in (ROLE_v1_0_1, ROLE_v1_1_0)) as v1_0_1_v1_1_0:
        v1_0_1_v1_1_0.npm_shrinkwrap = jsl.OneOfField(
            [jsl.DocumentField(NpmShrinkwrap, as_ref=True), jsl.NullField()])
    with jsl.Scope(lambda v: v < ROLE_v1_1_0) as before_v1_1_0:
        before_v1_1_0.maintainers = jsl.OneOfField(
                    [jsl.ArrayField(jsl.DocumentField(Maintainer, as_ref=True)), jsl.NullField()])
    with jsl.Scope(lambda v: v >= ROLE_v1_1_0) as since_v1_1_0:
        since_v1_1_0.contributors = jsl.OneOfField(
                    [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
        since_v1_1_0.maintainers = jsl.OneOfField(
                    [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
    with jsl.Scope(ROLE_v2_0_0) as v2_0_0:
        v2_0_0._system = jsl.StringField()
    with jsl.Scope(lambda v: v >= ROLE_v2_1_0 and v < ROLE_v3_0_0) as since_v2_1_0:
        since_v2_1_0._bayesian_dependency_tree_lock = jsl.OneOfField([
            jsl.DocumentField(LockFile, as_ref=True), jsl.NullField()
        ])
    with jsl.Scope(lambda v: v >= ROLE_v2_1_1) as since_v2_1_1:
        since_v2_1_1._tests_implemented = jsl.BooleanField()
    with jsl.Scope(lambda v: v >= ROLE_v3_0_0) as since_v3_0_0:
        since_v3_0_0.ecosystem = jsl.StringField()
        since_v3_0_0._dependency_tree_lock = jsl.OneOfField([
            jsl.DocumentField(LockFile, as_ref=True), jsl.NullField()
        ])


class MercatorResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "metadata"
        description = "Result of Mercator worker"

    # TODO: Any ideas how to reuse MetadataDict here ?
    with jsl.Scope(lambda v: v in (ROLE_v1_0_1, ROLE_v1_1_0)) as v1_0_1_v1_1_0:
        v1_0_1_v1_1_0.npm_shrinkwrap = jsl.OneOfField(
            [jsl.DocumentField(NpmShrinkwrap, as_ref=True), jsl.NullField()])
    with jsl.Scope(lambda v: v < ROLE_v1_1_0) as before_v1_1_0:
        before_v1_1_0.maintainers = jsl.OneOfField(
            [jsl.ArrayField(jsl.DocumentField(Maintainer, as_ref=True)), jsl.NullField()])
    with jsl.Scope(ROLE_v1_1_0) as v1_1_0:
        v1_1_0.contributors = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
        v1_1_0.maintainers = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
    with jsl.Scope(lambda v: v < ROLE_v2_0_0) as before_v2_0_0:
        # some of these may be missing in some ecosystem, so no required=True
        before_v2_0_0.author = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.bug_reporting = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.code_repository = jsl.OneOfField(
            [jsl.DocumentField(CodeRepository, as_ref=True), jsl.NullField()]
            )
        before_v2_0_0.declared_license = jsl.OneOfField(
            [jsl.StringField(), jsl.NullField()]
            )
        before_v2_0_0.dependencies = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
            )
        before_v2_0_0.description = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.devel_dependencies = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
            )
        # engines are NPM thingie and can contain lots of various keys
        # so we just allow pretty much anything in that dict
        before_v2_0_0.engines = jsl.OneOfField(
            [jsl.DictField(additional_properties=True), jsl.NullField()]
            )
        before_v2_0_0.files = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
            )
        before_v2_0_0.git_head = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.homepage = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.keywords = jsl.OneOfField(
            [jsl.ArrayField(jsl.StringField()), jsl.NullField()]
            )

        before_v2_0_0.maintainers = jsl.OneOfField(
                [jsl.ArrayField(jsl.StringField()), jsl.NullField()])

        # metadata is a rubygems thing and can contain arbitrary key/value pairs
        before_v2_0_0.metadata = jsl.OneOfField(
            [jsl.DictField(additional_properties=True), jsl.NullField()]
                )
        before_v2_0_0.name = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.platform = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
        before_v2_0_0.readme = jsl.OneOfField([jsl.StringField(), jsl.NullField()])

        before_v2_0_0.scripts = jsl.OneOfField(
            [jsl.DictField(additional_properties=True), jsl.NullField()]
            )
        before_v2_0_0.version = jsl.OneOfField([jsl.StringField(), jsl.NullField()])


# 2.0.0

    with jsl.Scope(ROLE_v2_0_0) as v2_0_0:
        v2_0_0.details = jsl.ArrayField(jsl.OneOfField(
            [jsl.DocumentField(MetadataDict, as_ref=True),
             jsl.DocumentField(NpmShrinkwrap, as_ref=True)]
        ))

# 2.1.0
    with added_in(ROLE_v2_1_0) as since_v2_1_0:
        since_v2_1_0.details = jsl.ArrayField(jsl.DocumentField(MetadataDict, as_ref=True))

# 3.1.0
    with added_in(ROLE_v3_1_0) as since_v3_1:
        since_v3_1.status = jsl.StringField(enum=["success", "error"], required=True)
        since_v3_1.summary = jsl.ArrayField(jsl.StringField(), required=True)

THE_SCHEMA = MercatorResult
