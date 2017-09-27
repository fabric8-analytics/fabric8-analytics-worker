"""JSL schema for license scan worker"""

import jsl
from f8a_worker.schemas import JSLSchemaBaseWithRelease, added_in, removed_in

ROLE_v1_0_0 = "v1-0-0"
ROLE_v2_0_0 = "v2-0-0"
ROLE_v3_0_0 = "v3-0-0"


class LicenseCount(jsl.Document):
    class Options(object):
        description = "Detected license with occurrence count"
        definition_id = "license_count"

    count = jsl.NumberField(
        description="Combined count of detected variants",
        required=True
    )
    license_name = jsl.StringField(
        description="Common name of the detected license",
        required=True
    )


class LicenseScanSummary(jsl.Document):
    class Options(object):
        definition_id = "license_scan_summary"

    with removed_in(ROLE_v3_0_0) as removed_in_v3_0_0:
        removed_in_v3_0_0.all_files = jsl.NumberField(description="Total number of files analysed")
        removed_in_v3_0_0.license_files = jsl.NumberField()
        removed_in_v3_0_0.source_files = jsl.NumberField()
        removed_in_v3_0_0.distinct_licenses = jsl.ArrayField(
            jsl.DocumentField(LicenseCount, as_ref=True),
            required=True
        )
        removed_in_v3_0_0.licensed_files = jsl.NumberField()

    sure_licenses = jsl.ArrayField(
        jsl.StringField(),
        description="Licenses detected with high match confidence",
        required=True
    )


class FileDetails(jsl.Document):
    class Options(object):
        definition_id = "file_details"

    path = jsl.StringField(required=True)
    result = jsl.ArrayField(jsl.DictField(additional_properties=True))


class LicenseDetailsPre30(jsl.Document):
    class Options(object):
        definition_id = "license_details_pre_3_0"

    with jsl.Scope(ROLE_v1_0_0) as v1_0_0:
        v1_0_0.count = jsl.StringField(
            description="Number of occurrences of this variant",
            required=True
        )
    with jsl.Scope(ROLE_v2_0_0) as v2_0_0:
        v2_0_0.count = jsl.NumberField(
            description="Number of occurrences of this variant",
            required=True
        )
    license_name = jsl.StringField(
        description="Common name of the detected license",
        required=True
    )
    variant_id = jsl.StringField(
        description="Specific license variant detected",
        required=True
    )


class LicenseDetails(jsl.Document):
    class Options(object):
        definition_id = "license_details"

    category = jsl.StringField(required=True)
    dejacode_url = jsl.StringField(required=True)
    homepage_url = jsl.StringField(required=True)
    owner = jsl.StringField(required=True)
    paths = jsl.ArrayField(jsl.StringField(), required=True)
    spdx_license_key = jsl.StringField(required=True)
    spdx_url = jsl.StringField(required=True)
    text_url = jsl.StringField(required=True)


class OSLCStats(jsl.Document):
    class Options(object):
        definition_id = "oslc_stats"
        additional_properties = True


class LicenseScanDetails(jsl.Document):
    class Options(object):
        definition_id = "license_scan_details"
        additional_properties = True

    with removed_in(ROLE_v3_0_0) as removed_in_v3_0_0:
        removed_in_v3_0_0.files = jsl.ArrayField(jsl.DocumentField(FileDetails, as_ref=True))
        removed_in_v3_0_0.license_stats = jsl.ArrayField(jsl.DocumentField(LicenseDetailsPre30,
                                                                           as_ref=True))
        removed_in_v3_0_0.oslc_stats = jsl.DocumentField(OSLCStats, as_ref=True)

    with added_in(ROLE_v3_0_0) as added_in_v3_0_0:
        added_in_v3_0_0.files_count = jsl.IntField(required=True)
        added_in_v3_0_0.licenses = jsl.DictField(pattern_properties=jsl.Var({
                                                    'role': {
                                                        '*': jsl.DocumentField(LicenseDetails,
                                                                               as_ref=True,
                                                                               required=True),
                                                    }}), required=True)
        added_in_v3_0_0.scancode_notice = jsl.StringField(required=True)
        added_in_v3_0_0.scancode_version = jsl.StringField(required=True)


class SuccessfulLicenseScan(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "successful_license_scan"
        description = "Successful automated software copyright license scan"

    status = jsl.StringField(enum=["success"], required=True)
    summary = jsl.DocumentField(LicenseScanSummary, as_ref=True, required=True)
    details = jsl.DocumentField(LicenseScanDetails, as_ref=True, required=True)


class FailedLicenseScan(JSLSchemaBaseWithRelease):
    class Options(object):
        definition_id = "failed_license_scan"
        description = "Failed automated software copyright license scan"

    status = jsl.StringField(enum=["error"], required=True)
    summary = jsl.DictField(required=True, additional_properties=True)
    details = jsl.DictField(required=True, additional_properties=True)


class LicenseScanResult(SuccessfulLicenseScan, FailedLicenseScan):
    class Options(object):
        definition_id = "source_licenses"
        inheritance_mode = jsl.ONE_OF


THE_SCHEMA = LicenseScanResult
