"""JSL schema for Binwalk worker results."""

import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Binary Data v1-0-0"
})


class BinwalkDetail(jsl.Document):
    """JSL schema for Binwalk worker results details."""

    class Options(object):
        """JSL schema for Binwalk worker results details."""

        definition_id = "binwalk_details"
        description = "Details of Binwalk run on one file"

    path = jsl.StringField(required=True)
    output = jsl.ArrayField(jsl.StringField(), required=True)


class BinwalkResult(JSLSchemaBaseWithRelease):
    """JSL schema for Binwalk worker results."""

    class Options(object):
        """JSL schema for Binwalk worker results."""

        definition_id = "binary_data"
        description = "Result of Binwalk worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.ArrayField(
            jsl.DocumentField(BinwalkDetail, as_ref=True),
            required=True
    )
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = BinwalkResult
