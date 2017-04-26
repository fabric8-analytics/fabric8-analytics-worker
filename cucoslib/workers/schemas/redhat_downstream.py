"""JSL schema for Red Hat downstream usage query results"""
import jsl
from collections import OrderedDict

from cucoslib.schemas import JSLSchemaBaseWithRelease, added_in, removed_in

ROLE_v1_0_0 = "v1-0-0"
ROLE_v2_0_0 = "v2-0-0"
ROLE_v2_1_0 = "v2-1-0"
ROLE_v2_2_0 = "v2-2-0"
ROLE_v2_2_1 = "v2-2-1"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "Red Hat Downstream Components v1-0-0",
    ROLE_v2_0_0: "Red Hat Downstream Components v2-0-0",
    ROLE_v2_1_0: "Red Hat Downstream Components v2-1-0",
    ROLE_v2_2_0: "Red Hat Downstream Components v2-2-0",
    ROLE_v2_2_1: "Red Hat Downstream Components v2-2-1",
})
# Schema change history
# v2-0-0 (Initial Brew and Pulp CDN metadata inclusion)
#    "published_in" added to individual SRPM records
#    "published_in" removed from overall result summary
# v2-1-0 (Improvements & fixes for Pulp CDN metadata inclusion)
#    "pulp_cdn" details field redefined as an array
#     required "srpm_filename" field added to Pulp CDN details entries
#    "published_in" now lists RHSM Content Sets, not RHN Channels
#    "all_rhn_channels" added to overall result summary
#    "all_rhsm_content_sets" added to overall result summary
# v2-2-0 (Added RHSM product names)
#    "rhn_channels" explicitly added to Pulp CDN records
#    "rhsm_content_sets" explicitly added to Pulp CDN records
#    "rhsm_product_names" added to Pulp CDN records
#    "published_in" now lists RHSM Product Names, not Content Sets
#    "all_rhsm_product_names" added to overall result summary


class AnityaResponse(jsl.Document):
    class Options(object):
        definition_id = "anitya_response"
        description = "Anitya maps upstream components to downstream packages"
        additional_properties = True


class KojiResponse(jsl.Document):
    class Options(object):
        definition_id = "koji_response"
        description = "Koji is an SRPM build system used by Fedora and Red Hat"
        additional_properties = True


class PulpCDNResponse(jsl.Document):
    class Options(object):
        definition_id = "pulp_cdn_response"
        description = "The Pulp CDN handles Red Hat's SRPM publication"
        additional_properties = True

    with added_in(ROLE_v2_1_0) as since_v2_1:
        since_v2_1.srpm_filename = jsl.StringField(required=True)
    with added_in(ROLE_v2_2_0) as since_v2_2:
        since_v2_2.rhn_channels = jsl.ArrayField(jsl.StringField(),
                                                 required=True)
        since_v2_2.rhsm_content_sets = jsl.ArrayField(jsl.StringField(),
                                                      required=True)
        since_v2_2.rhsm_product_names = jsl.ArrayField(jsl.StringField(),
                                                       required=True)


class ChangeDefinition(jsl.Document):
    class Options(object):
        definition_id = "changes"
        description = "Breakdown of changed lines per given file"

    lines = jsl.ArrayField(jsl.StringField(), required=True)
    file = jsl.StringField(required=True)


class DiffDefinition(jsl.Document):
    class Options(object):
        definition_id = "diff"
        description = "Information about changed files and lines"

    files = jsl.IntField(required=True)
    lines = jsl.IntField(required=True)
    changes = jsl.ArrayField(jsl.DocumentField(ChangeDefinition, as_ref=True), required=True)


class DownstreamPatchset(jsl.Document):
    class Options(object):
        definition_id = "downstream"
        description = "Patch information about downstream SRPM"

    diff = jsl.DocumentField(DiffDefinition, as_ref=True, required=True)
    patch_files = jsl.ArrayField(jsl.StringField(), required=True)
    package = jsl.StringField(required=True)


class ToolchainResponses(jsl.Document):
    class Options(object):
        definition_id = "toolchain_responses"

    # These fields are optional, as this spec currently covers error responses
    # in addition to successful toolchain queries.
    # They can change to being required once the "standard error schema" RFE
    # is implemented: https://github.com/baytemp/worker/issues/109

    redhat_anitya = jsl.DocumentField(
        AnityaResponse,
        description="Results from Red Hat's internal Anitya instance",
        required=False,
        as_ref=True
    )
    brew = jsl.ArrayField(jsl.DocumentField(
        DownstreamPatchset,
        description="Results from Brew, Red Hat's internal Koji instance",
        required=False,
        as_ref=True
    ))
    # The Pulp CDN details field became an array in v2-1-0
    _pulp_document_ref = jsl.DocumentField(
            PulpCDNResponse,
            description="Results from the Pulp CDN backing RPM delivery",
            required=False,
            as_ref=True
    )
    with removed_in(ROLE_v2_1_0) as before_v2_1:
        before_v2_1.pulp_cdn = _pulp_document_ref
    with added_in(ROLE_v2_1_0) as since_v2_1:
        since_v2_1.pulp_cdn = jsl.ArrayField(_pulp_document_ref)
    del _pulp_document_ref



class SRPMRecord(jsl.Document):
    class Options(object):
        definition_id = "srpm_record"
        description = "Summary of Red Hat tracked SRPM"

    # Proposed contents, TBC by Brew query integration work
    package_name = jsl.StringField(required=True)
    epoch = jsl.NumberField(required=True)
    version = jsl.StringField(required=True)
    release = jsl.StringField(required=True)
    patch_count = jsl.NumberField(required=True)
    modified_line_count = jsl.NumberField(required=True)
    modified_file_count = jsl.NumberField(required=True)
    with added_in(ROLE_v2_0_0) as since_v2_0:
        since_v2_0.published_in = jsl.ArrayField(jsl.StringField())
    tags = jsl.ArrayField(jsl.StringField()) # Maybe?
    architectures = jsl.ArrayField(jsl.StringField()) # Maybe?
    hashes = jsl.DictField(properties=OrderedDict((
        ("md5", jsl.StringField()),
        ("sha1", jsl.StringField()),
        ("sha256", jsl.StringField()),
    ))) # Maybe?


class DownstreamUsageSummary(jsl.Document):
    class Options(object):
        definition_id = "downstream_usage_summary"

    package_names = jsl.ArrayField(jsl.StringField(), required=True)
    # Brew query integration
    registered_srpms = jsl.ArrayField(
             jsl.DocumentField(SRPMRecord, as_ref=True),
             required=True
    )
    # Pulp CDN query integration
    with jsl.Scope(ROLE_v1_0_0) as v1:
        v1.published_in = jsl.ArrayField(jsl.StringField(), required=True)
    with added_in(ROLE_v2_1_0) as since_v2_1:
        since_v2_1.all_rhn_channels = jsl.ArrayField(jsl.StringField(),
                                                     required=True)
        since_v2_1.all_rhsm_content_sets = jsl.ArrayField(jsl.StringField(),
                                                          required=True)
    with added_in(ROLE_v2_2_0) as since_v2_2:
        since_v2_2.all_rhsm_product_names = jsl.ArrayField(jsl.StringField(),
                                                           required=True)
    with added_in(ROLE_v2_2_1) as since_v2_2_1:
        since_v2_2_1.rh_mvn_matched_versions = jsl.ArrayField(jsl.StringField(),
                                                              required=True)


class DownstreamUsageResult(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "downstream_usage_result"
        description = "Result of DownstreamUsage worker"

    status = jsl.StringField(enum = ["success", "error"], required=True)
    details = jsl.DocumentField(ToolchainResponses, as_ref=True)
    summary = jsl.DocumentField(
        DownstreamUsageSummary,
        as_ref=True,
        required=True
    )

THE_SCHEMA = DownstreamUsageResult
