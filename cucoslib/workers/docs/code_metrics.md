Code metrics worker
-------------------

As the result of the code metrics worker is highly dependent on languages that were found, we are limited to language-specific metrics that can be computed for a language.

Currently the code metrics worker supports generic code metrics as reported by [`cloc`](https://github.com/AlDanial/cloc) tool (currently supported cca 200 languages). The output consist of the following entries (example for Java):

```json
{
    "blank_lines": 13,
    "code_lines": 178,
    "comment_lines": 6,
    "files_count": 1,
    "language": "Java"
}
```

To have more detailed statistics, there was added additional support for Java and JavaScript languages. These statistics are computed by [JavaNCSS](http://www.kclee.de/clemens/java/javancss/) in case of Java and [complexity-report](https://github.com/escomplex/complexity-report) in case of JavaScript. Results of these tools are parsed to the resulting JSON, that can be found under `metrics` key for the given language entry:

```json
{
    "blank_lines": 13,
    "code_lines": 178,
    "comment_lines": 6,
    "files_count": 1,
    "language": "Java"
    "metrics": {
    
    }
}
```

## JavaScript

Here is a part of JavaScript-specific entries for `serve-static` in version `1.7.1` that are computed (each list consists of one representative example entry):

```json
"metrics": {

    "average_cyclomatic_complexity": null,
    "average_function_lines_of_code": null,
    "average_function_parameters_count": null,
    "average_halstead_effort": null,
    "cost_change": 100,
    "first_order_density": null,
    "modules": [
        {
            "average_function_lines_of_code": null,
            "average_function_parameters_count": null,
            "dependencies": [
                {
                    "line": 13,
                    "path": "escape-html",
                    "type": "CommonJS"
                }
            ],
            "functions": [
                {
                    "cyclomatic": 6,
                    "cyclomatic_density": 42.857142857142854,
                    "halstead": {
                        "bugs": 0.13566567576667574,
                        "difficulty": 18.22222222222222,
                        "effort": 7416.390275244939,
                        "length": 80,
                        "operands": {
                            "distinct": 18,
                            "identifiers": [
                                "root",
                                "TypeError"
                            ],
                            "total": 41
                        },
                        "operators": {
                            "distinct": 16,
                            "identifiers": [
                                "if",
                                "throw",
                                "new"
                            ],
                            "total": 39
                        },
                        "time": 412.02168195805217,
                        "vocabulary": 34,
                        "volume": 406.9970273000272
                    },
                    "line": 27,
                    "name": "serveStatic",
                    "params": 2,
                    "sloc": {
                        "logical": 14,
                        "physical": 83
                    }
                }
            ],
            "module_maintainability": 104.68951553775626,
            "path": "package/index.js"
        }
    ],
    "project_maintainability": 104.68951553775626
}
```

See [`complexity-report` documentation](https://github.com/escomplex/escomplex/blob/master/README.md) for better understanding of the computed metrics.


## Java

The following example demonstrates Java-specific entries computed for `net.iharder:base64` in version `2.3.9` (one list entry representative in each list):

```json
"metrics": {
    "functions": {
        "average_cyclomatic_complexity": 5.37,
        "average_javadocs": 0.98,
        "function": [
            {
                "cyclomatic_complexity": 5,
                "javadocs": 1,
                "name": "net.iharder.Base64.getAlphabet(int)"
            }
        ]
    },
    "objects": {
        "average_classes": 0.75,
        "average_functions": 10.25,
        "average_javadocs": 13.75,
        "object": [
            {
                "classes": 3,
                "functions": 28,
                "javadocs": 43,
                "name": "net.iharder.Base64"
            }
        ]
    },
    "packages": {
        "classes": 4,
        "functions": 41,
        "javadoc_lines": 690,
        "javadocs": 43,
        "multi_comment_lines": 61,
        "single_comment_lines": 401
    }
}
```

Refer to [`JavaNCSS` documentation](http://www.kclee.de/clemens/java/javancss/#specification) for more info about the computed metrics.
