"""JSL schema for license scan worker"""
import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

ROLE_v1_0_0 = "v1-0-0"
ROLE_v2_0_0 = "v2-0-0"

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

    all_files = jsl.NumberField(description="Total number of files analysed")
    license_files = jsl.NumberField()
    source_files = jsl.NumberField()
    distinct_licenses = jsl.ArrayField(
        jsl.DocumentField(LicenseCount, as_ref=True),
        required=True
    )
    sure_licenses = jsl.ArrayField(
        jsl.StringField(),
        description="Licenses detected with high match confidence",
        required=True
    )
    licensed_files = jsl.NumberField()


class FileDetails(jsl.Document):
    class Options(object):
        definition_id = "file_details"

    path = jsl.StringField(required=True)
    result = jsl.ArrayField(jsl.DictField(additional_properties=True))


class LicenseDetails(jsl.Document):
    class Options(object):
        definition_id = "license_details"

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


class OSLCStats(jsl.Document):
    class Options(object):
        definition_id = "oslc_stats"
        additional_properties = True


class LicenseScanDetails(jsl.Document):
    class Options(object):
        definition_id = "license_scan_details"
        additional_properties = True

    files = jsl.ArrayField(jsl.DocumentField(FileDetails, as_ref=True))
    license_stats = jsl.ArrayField(jsl.DocumentField(LicenseDetails, as_ref=True))
    oslc_stats = jsl.DocumentField(OSLCStats, as_ref=True)

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
