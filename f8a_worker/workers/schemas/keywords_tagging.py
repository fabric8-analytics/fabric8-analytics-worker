"""JSL schema for keywords tagging worker."""
import jsl
from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Keywords tagging v1-0-0"
})


class KeywordsTaggingDetails(jsl.Document):
    class Options(object):
        definition_id = "keywords_tagging_details"
        description = "Details computed by KeywordsTagging worker"

    description = jsl.DictField(required=False, additional_properties=True)
    # Keywords extracted in mercator (e.g. keywords stated in setup.py)
    keywords = jsl.ArrayField(jsl.StringField())


class KeywordsTaggingResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "keywords_tagging"
        description = "Result of KeywordsTagging worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.DocumentField(KeywordsTaggingDetails, as_ref=True, required=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = KeywordsTaggingResult
