# Support for Various Ecosystems in Workers

This document contains an Ecosystem/Worker support matrix with notes about specialties/exceptions on how various workers work with different ecosystems.
The workers are referred to as `<name of Python module>.<name of Python Class>`.
Workers not included here are ecosystem agnostic.

| Worker/Ecosystem                             | npm                                | maven                              | pypi                               | nuget                              |
|----------------------------------------------|------------------------------------|------------------------------------|------------------------------------|------------------------------------|
| `anitya.AnityaTask`                          | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :negative_squared_cross_mark:
| `bigquery.BigQueryTask`                      | :white_check_mark:                 | :negative_squared_cross_mark:  (1) | :negative_squared_cross_mark:      | :grey_question:
| `binwalk.BinwalkTask`                        | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :grey_exclamation:  (5)
| `blackduck.BlackDuckTask`                    | :white_check_mark:                 | :grey_question:                    | :white_check_mark:                 | :grey_question:
| `code_metrics.CodeMetricsTask`               | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :grey_exclamation:  (5)
| `csmock_worker.CsmockTask`                   | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :grey_exclamation:  (5)
| `CVEchecker.CVEcheckerTask`                  | :white_check_mark:                 | :grey_exclamation:  (2)            | :white_check_mark:                 | :white_check_mark:
| `dependency_snapshot.DependencySnapshotTask` | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `digester.DigesterTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `downstream.DownstreamUsageTask`             | :white_check_mark:                 | :grey_exclamation:  (3)            | :white_check_mark:                 | :negative_squared_cross_mark:
| `finalize.FinalizeTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `githuber.GithubTask`                        | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `init_analysis_flow.InitAnalysisFlow`        | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `license.LicenseCheckTask`                   | :white_check_mark:                 | :grey_exclamation:  (4)            | :white_check_mark:                 | :grey_exclamation:  (5)
| `linguist.LinguistTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :grey_exclamation:  (5)
| `mercator.MercatorTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:
| `oscryptocatcher.OSCryptoCatcher`            | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 | :grey_question:


**(1)**: Due to `pom.xml` dynamic nature (they support templating and inheritance, but we can't expand them in BigQuery queries, so the data that we'd get would be partial and possibly misleading.

**(2)**: CVE checker theoretically works, but the problem is that component naming in the CVE DB is very inaccurate/random for Java. E.g. for `org.apache.taglibs:taglibs-standard-spec` component, the CVE DB contains `apache:standard_taglibs`. There's pretty much no way to match these with a decent certainty.

**(3)**: Right now, we only gather downstream usage data based on virtual provides `mvn(groupId:artifactId)` from RHEL 7 (also see `downstream/downstream-data-import.py` for how DB is initialized with this data).

**(4)**: License extraction from source code only works for Maven artifacts assuming the upstream uploaded sources to Maven Central; otherwise we only have information from `pom.xml`.

**(5)**: Nuget packages do not contain source code, only dll libraries along with metadata and license file (in some cases), so workers, which expect source code, don't work as expected.
