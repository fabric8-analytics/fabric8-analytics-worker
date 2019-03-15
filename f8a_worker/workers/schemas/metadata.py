"""JSL schemas for Mercator worker results."""

import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

ROLE_v4_0_0 = "v4-0-0"
ROLE_TITLE = jsl.roles.Var({
    # clean up; look for older schema definitions in git history ;)
    # allow additional properties in LockFile/LockedDependency
    ROLE_v4_0_0: "Package Metadata v4-0-0",
})


class CodeRepository(jsl.Document):
    """JSL schema for code repository description."""

    class Options(object):
        """JSL schema for code repository description."""

        definition_id = "metadata_code_repository"
        description = "Code repository description"

    type = jsl.StringField(required=False)
    url = jsl.StringField(required=True)


class Maintainer(jsl.Document):
    """JSL schema for maintainer description."""

    class Options(object):
        """JSL schema for maintainer description."""

        definition_id = "metadata_maintainer"
        description = "Maintainer description"

    name = jsl.StringField()
    email = jsl.StringField()
    url = jsl.StringField()


class LockedDependency(jsl.Document):
    """JSL schema for locked dependency description."""

    class Options(object):
        """JSL schema for locked dependency description."""

        definition_id = "metadata_locked_dependency"
        description = "Locked dependency description"
        additional_properties = True

    name = jsl.StringField()
    version = jsl.StringField()
    specification = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    resolved = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    dependencies = jsl.ArrayField(jsl.DocumentField(jsl.RECURSIVE_REFERENCE_CONSTANT, as_ref=True))
    # go glide
    subpackages = jsl.ArrayField(jsl.StringField())


class LockFile(jsl.Document):
    """JSL schema for dependency lock file description."""

    class Options(object):
        """JSL schema for dependency lock file description."""

        definition_id = "metadata_lockfile"
        description = "Dependency lock file description"
        additional_properties = True

    runtime = jsl.StringField()
    version = jsl.StringField()
    dependencies = jsl.ArrayField(jsl.DocumentField(LockedDependency, as_ref=True))
    name = jsl.StringField()

    # go glide
    hash = jsl.StringField()
    updated = jsl.StringField()


class NpmShrinkwrap(jsl.Document):
    """JSL schema for npm-shrinkwrap description."""

    class Options(object):
        """JSL schema for npm-shrinkwrap description."""

        definition_id = "npm_shrinkwrap"
        description = "npm-shrinkwrap description"

    name = jsl.StringField()
    version = jsl.StringField()
    npm_shrinkwrap_version = jsl.StringField()
    node_version = jsl.StringField()
    resolved_dependencies = jsl.ArrayField(jsl.StringField())
    dependencies = jsl.ArrayField(jsl.StringField())
    _system = jsl.StringField()


class MetadataDict(jsl.Document):
    """JSL schema for generic metadata dict in details list."""

    class Options(object):
        """JSL schema for generic metadata dict in details list."""

        definition_id = "details_metadata"
        description = "generic metadata dict in details list"

    # some of these may be missing in some ecosystem, so no required=True

    # 'author' should have been list of 'authors', but it's too late now
    author = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    bug_reporting = jsl.OneOfField([jsl.StringField(), jsl.NullField()])
    code_repository = jsl.OneOfField(
        [jsl.DocumentField(CodeRepository, as_ref=True), jsl.NullField()]
    )

    declared_licenses = jsl.OneOfField([jsl.ArrayField(
        jsl.StringField()),
        jsl.NullField()]
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

    contributors = jsl.OneOfField(
                    [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
    maintainers = jsl.OneOfField(
                    [jsl.ArrayField(jsl.StringField()), jsl.NullField()])
    _tests_implemented = jsl.BooleanField()
    ecosystem = jsl.StringField()
    _dependency_tree_lock = jsl.OneOfField([
        jsl.DocumentField(LockFile, as_ref=True), jsl.NullField()
    ])
    path = jsl.OneOfField(
        [jsl.StringField(), jsl.NullField()],
        required=False
    )


class MercatorResult(JSLSchemaBaseWithRelease):
    """JSL schema for Mercator worker results."""

    class Options(object):
        """JSL schema for Mercator worker results."""

        definition_id = "metadata"
        description = "Result of Mercator worker"

    details = jsl.ArrayField(jsl.DocumentField(MetadataDict, as_ref=True))

    status = jsl.StringField(enum=["success", "error"], required=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = MercatorResult
