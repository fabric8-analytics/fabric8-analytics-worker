import jsl

from cucoslib.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Digests v1-0-0"
})


class DigesterDetail(jsl.Document):
    class Options(object):
        definition_id = "digester_details"
        description = "Details of Digester run on one file"

    artifact = jsl.BooleanField()  # not required
    path = jsl.StringField(required=True)
    ssdeep = jsl.StringField(required=True)
    md5 = jsl.StringField(required=True)
    sha1 = jsl.StringField(required=True)
    sha256 = jsl.StringField(required=True)


class DigesterResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "digests"
        description = "Result of Digester worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.ArrayField(
            jsl.DocumentField(DigesterDetail, as_ref=True),
            required=True
    )
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = DigesterResult
