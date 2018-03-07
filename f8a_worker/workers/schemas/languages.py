"""JSL schema for Linguist worker results."""

import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Languages Information v1-0-0"
})


class LinguistOutput(jsl.Document):
    """JSL schema for Linguist output for one file."""

    class Options(object):
        """JSL schema for Linguist output for one file."""

        definition_id = "linguist_output"
        description = "Linguist output for one file"

    lines = jsl.IntField(required=True)
    sloc = jsl.IntField(required=True)
    type = jsl.StringField(required=True)
    language = jsl.StringField(required=True)
    mime = jsl.StringField(required=True)


class LinguistDetail(jsl.Document):
    """JSL schema for Linguist worker results details."""

    class Options(object):
        """JSL schema for Linguist worker results details."""

        definition_id = "linguist_details"
        description = "Details of Linguist run on one file"

    path = jsl.StringField(required=True)
    output = jsl.OneOfField(
        [jsl.DocumentField(LinguistOutput, as_ref=True), jsl.NullField()],
        required=True
    )
    type = jsl.ArrayField(jsl.StringField(), required=True)


class LinguistResult(JSLSchemaBaseWithRelease):
    """JSL schema for Linguist worker results."""

    class Options(object):
        """JSL schema for Linguist worker results."""

        definition_id = "languages"
        description = "Result of Linguist worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.ArrayField(
        jsl.DocumentField(LinguistDetail, as_ref=True),
        required=True
    )
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = LinguistResult
