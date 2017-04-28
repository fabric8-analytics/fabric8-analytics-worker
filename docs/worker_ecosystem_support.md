# Support for Various Ecosystems in Workers

This document contains an Ecosystem/Worker support matrix with notes about specialties/exceptions on how various workers work with different ecosystems. The workers are referred to as `<name of Python module>.<name of Python Class>`.

| Worker/Ecosystem                             | npm                                | maven                              | pypi                               |
|----------------------------------------------|------------------------------------|------------------------------------|------------------------------------|
| `anitya.AnityaTask`                          | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `bigquery.BigQueryBeat`                      | :white_check_mark:                 | :negative_squared_cross_mark:  (1) | :negative_squared_cross_mark:      |
| `binwalk.BinwalkTask`                        | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `blackduck.BlackDuckTask`                    | :white_check_mark:                 | TODO                               | :white_check_mark:                 |
| `CVEchecker.CVEcheckerTask`                  | :white_check_mark:                 | :grey_exclamation:  (2)            | :white_check_mark:                 |
| `code_metrics.CodeMetricsTask`               | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `dependency_snapshot.DependencySnapshotTask` | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `digester.DigesterTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `downstream.DownstreamUsageTask`             | :white_check_mark:                 | :grey_exclamation:  (3)            | :white_check_mark:                 |
| `finalize.FinalizeTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `githuber.GithubTask`                        | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `init.InitAnalysisFlow`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `license.LicenseCheckTask`                   | :white_check_mark:                 | :grey_exclamation:  (4)            | :white_check_mark:                 |
| `linguist.LinguistTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `mercator.AggregatingMercatorTask`           | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `mercator.DependencyAggregatorTask`          | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `mercator.MercatorTask`                      | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |
| `oscryptocatcher.OSCryptoCatcher`            | :white_check_mark:                 | :white_check_mark:                 | :white_check_mark:                 |

**(1)**: Due to `pom.xml` dynamic nature (they support templating and inheritance, but we can't expand them in BigQuery queries, so the data that we'd get would be partial and possibly misleading.

**(2)**: CVE checker theoretically works, but the problem is that component naming in the CVE DB is very inaccurate/random for Java. E.g. for `org.apache.taglibs:taglibs-standard-spec` component, the CVE DB contains `apache:standard_taglibs`. There's pretty much no way to match these with a decent certainty.

**(3)**: Right now, we only gather downstream usage data based on virtual provides `mvn(groupId:artifactId)` from RHEL 7 (also see `downstream/downstream-data-import.py` for how DB is initialized with this data).

**(4)**: License extraction from source code only works for Maven artifacts assuming the upstream uploaded sources to Maven Central; otherwise we only have information from `pom.xml`.
