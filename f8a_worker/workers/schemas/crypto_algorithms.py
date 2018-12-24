"""JSL schema for OSCrypto catcher worker."""

import jsl

from f8a_worker.schemas import JSLSchemaBaseWithRelease

# Describe v1-0-0
ROLE_v1_0_0 = "v1-0-0"
ROLE_TITLE = jsl.roles.Var({
    ROLE_v1_0_0: "OSCrypto catcher v1-0-0"
})


class CryptoAlgoDetail(jsl.Document):
    """JSL schema for cryptoalgo_detail."""

    class Options(object):
        """JSL schema for cryptoalgo_detail."""

        definition_id = "cryptoalgo_detail"

    crypto = jsl.StringField(required=True)
    file = jsl.StringField(required=True)
    matched_lines = jsl.NumberField()
    matchpercent = jsl.NumberField()
    matchtype = jsl.StringField(enum=["content", "filename"], required=True)
    sample_file = jsl.StringField()
    samples_lines = jsl.NumberField()


class CryptoAlgorithmRecord(jsl.Document):
    """JSL schema for cryptoalgo_record."""

    class Options(object):
        """JSL schema for cryptoalgo_record."""

        definition_id = "cryptoalgo_record"

    count = jsl.NumberField(required=True)
    name = jsl.StringField(required=True)


class CryptoCheckSummary(jsl.Document):
    """JSL schema for OSCrypto catcher worker results summary."""

    class Options(object):
        """JSL schema for OSCrypto catcher worker results summary."""

        definition_id = "cryptocheck_summary"

    content = jsl.ArrayField(
            jsl.DocumentField(CryptoAlgorithmRecord, as_ref=True),
            required=True
    )
    filename = jsl.ArrayField(
             jsl.DocumentField(CryptoAlgorithmRecord, as_ref=True),
             required=True
    )


class CryptoCheckResult(JSLSchemaBaseWithRelease):
    """JSL schema for OSCrypto catcher worker results."""

    class Options(object):
        """JSL schema for OSCrypto catcher worker results."""

        definition_id = "crypto_algorithms_result"
        description = "Result of OSCryptoChecker worker"

    status = jsl.StringField(enum=["success", "error"], required=True)
    details = jsl.ArrayField(
            jsl.DocumentField(CryptoAlgoDetail, as_ref=True),
            required=True
    )
    summary = jsl.DocumentField(
            CryptoCheckSummary,
            as_ref=True,
            required=True
    )


THE_SCHEMA = CryptoCheckResult
