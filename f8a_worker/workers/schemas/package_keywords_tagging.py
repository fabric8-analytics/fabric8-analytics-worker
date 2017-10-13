"""JSL schema for keywords tagging worker."""
import jsl
from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Package keywords tagging v1-0-0"
})


class PackageKeywordsTaggingDetails(jsl.Document):
    class Options(object):
        definition_id = "package_keywords_tagging_details"
        description = "Details computed by PackageKeywordsTagging worker"

    README = jsl.DictField(required=False, dditional_properties=True)
    package_name = jsl.DictField(required=False, additional_properties=True)
    repository_description = jsl.DictField(required=False, additional_properties=True)
    gh_topics = jsl.ArrayField(jsl.StringField(), required=False)


class PackageKeywordsTaggingResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "package_keywords_tagging"
        description = "Result of PackageKeywordsTagging worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.DocumentField(PackageKeywordsTaggingDetails, as_ref=True, required=True)
    summary = jsl.ArrayField(jsl.StringField(), required=True)


THE_SCHEMA = PackageKeywordsTaggingResult
