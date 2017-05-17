"""JSL schema for cvechecker worker"""
import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease, added_in, removed_in

ROLE_v1_0_0 = "v1-0-0"
ROLE_v2_0_0 = "v2-0-0"
ROLE_v3_0_0 = "v3-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "CVE checker v1-0-0",
    ROLE_v2_0_0: "CVE checker v2-0-0",
    ROLE_v3_0_0: "CVE checker v3-0-0"
})


class CVEImpact(jsl.Document):
    class Options(object):
        definition_id = "cve_impact"

    with jsl.Scope(ROLE_v1_0_0) as v1:
        v1.availability = jsl.StringField(enum=["NONE", "LOW", "HIGH"], required=True)
    with jsl.Scope(ROLE_v2_0_0) as v2:
        v2.availability = jsl.StringField(enum=["NONE", "PARTIAL", "COMPLETE"], required=True)
    confidentiality = jsl.StringField(enum=["NONE", "PARTIAL", "COMPLETE"], required=True)
    integrity = jsl.StringField(enum=["NONE", "PARTIAL", "COMPLETE"], required=True)


class CVEAccess(jsl.Document):
    class Options(object):
        definition_id = "cve_access"

    authentication = jsl.StringField(enum=["NONE", "SINGLE", "MULTIPLE"], required=True)
    complexity = jsl.StringField(enum=["LOW", "MEDIUM", "HIGH"], required=True)
    with jsl.Scope(ROLE_v1_0_0) as v1:
        v1.vector = jsl.StringField(enum=["NETWORK", "ADJACENT NETWORK", "LOCAL"], required=True)
    with jsl.Scope(ROLE_v2_0_0) as v2:
        v2.vector = jsl.StringField(enum=["NETWORK", "ADJACENT_NETWORK", "LOCAL"], required=True)


class CVSS(jsl.Document):
    class Options(object):
        definition_id = "cvss"

    score = jsl.NumberField(required=True)
    vector = jsl.StringField(required=True)


class CVEDetail(jsl.Document):
    class Options(object):
        definition_id = "cvecheck_details"
        description = "Detail of one CVE"

    with removed_in(ROLE_v3_0_0) as removed_in_v3_0_0:
        # access/impact are now part of vector string in cvss dict
        removed_in_v3_0_0.access = jsl.DocumentField(CVEAccess, as_ref=True, required=True)
        removed_in_v3_0_0.impact = jsl.DocumentField(CVEImpact, as_ref=True, required=True)
        removed_in_v3_0_0.cvss = jsl.NumberField(required=True)  # cvss is now dict
        removed_in_v3_0_0.summary = jsl.StringField(required=True)  # renamed to description

    with added_in(ROLE_v3_0_0) as added_in_v3_0_0:
        added_in_v3_0_0.cvss = jsl.DocumentField(CVSS, as_ref=True, required=True)
        added_in_v3_0_0.description = jsl.StringField(required=True)
        added_in_v3_0_0.severity = jsl.StringField(required=True)

    id = jsl.StringField(required=True)
    references = jsl.ArrayField(jsl.UriField(), required=True)
    # Present if defined for the particular CVE
    cwe = jsl.StringField(required=False)


class CVECheckResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "cvecheck_results"
        description = "CVEcheck worker results"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.ArrayField(
            jsl.DocumentField(CVEDetail, as_ref=True),
            required=True
    )
    summary = jsl.ArrayField(jsl.StringField(), required=True)

THE_SCHEMA = CVECheckResult
