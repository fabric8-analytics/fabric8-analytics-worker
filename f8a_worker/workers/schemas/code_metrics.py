"""JSL schema for Code metrics worker."""

import jsl
from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Code metrics v1-0-0"
})


class CodeMetricsLanguage(jsl.Document):
    """JSL schema for Generic language specific statistics."""

    class Options(object):
        """JSL schema for Generic language specific statistics."""

        definition_id = "languages"
        description = "Generic language specific statistics"

    blank_lines = jsl.NumberField(required=True)
    code_lines = jsl.NumberField(required=True)
    comment_lines = jsl.NumberField(required=True)
    files_count = jsl.NumberField(required=True)
    language = jsl.StringField(required=True)
    # Might be language-specific once we add support for new languages, leave it generic for now
    metrics = jsl.DictField(required=False, additional_properties=True)


class CodeMetricsDetails(jsl.Document):
    """JSL schema for Code metrics worker results details."""

    class Options(object):
        """JSL schema for Code metrics worker results details."""

        definition_id = "code_metrics_result"
        description = "Details computed by CodeMetrics worker"

    languages = jsl.ArrayField(
        jsl.DocumentField(CodeMetricsLanguage, as_ref=True),
        required=True
    )


class CodeMetricsSummary(jsl.Document):
    """JSL schema for Code metrics worker results summary."""

    class Options(object):
        """JSL schema for Code metrics worker results summary."""

        definition_id = "code_metrics_summary"
        description = "Summary computed by CodeMetrics worker"

    blank_lines = jsl.NumberField(required=True)
    code_lines = jsl.NumberField(required=True)
    comment_lines = jsl.NumberField(required=True)
    total_files = jsl.NumberField(required=True)
    total_lines = jsl.NumberField(required=True)


class CodeMetricsResult(JSLSchemaBaseWithRelease):
    """JSL schema for Code metrics worker."""

    class Options(object):
        """JSL schema for Code metrics worker."""

        definition_id = "crypto_algorithms_result"
        description = "Result of CodeMetrics worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.DocumentField(CodeMetricsDetails, as_ref=True, required=True)
    summary = jsl.DocumentField(CodeMetricsSummary, as_ref=True, required=True)


THE_SCHEMA = CodeMetricsResult
