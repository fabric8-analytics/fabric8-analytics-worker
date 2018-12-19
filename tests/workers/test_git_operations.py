"""Test git_operations."""

from f8a_worker.workers import git_operations as go
import json

npmlist = {
    "name": "nice-package",
    "version": "3.0.3",
    "dependencies": {
        "github-url-to-object": {
            "version": "4.0.4",
            "from": "github-url-to-object@4.0.4",
            "resolved": "https://registry.npmjs.org/github-url-to-object-4.0.4.tgz",
            "dependencies": {
                "is-url": {
                    "version": "1.2.4",
                    "from": "is-url@^1.1.0",
                    "resolved": "https://registry.npmjs.org/is-url/-/is-url-1.2.4.tgz",
                    "dependencies": {
                        "ms": {
                            "version": "2.0.0",
                            "from": "ms@2.0.0",
                            "resolved": "https://registry.npmjs.org/ms/-/ms-2.0.0.tgz"
                        }
                    }

                }
            }
        },
        "lodash": {
            "version": "4.17.10",
            "from": "lodash@^4.17.2",
            "resolved": "https://registry.npmjs.org/lodash/-/lodash-4.17.10.tgz"
        },
        "normalize-registry-metadata": {
            "version": "1.1.2",
            "from": "normalize-registry-metadata@^1.1.2",
            "resolved": "https://registry.npmjs.org/normalize-registry-metadata-1.1.2.tgz",
            "dependencies": {
                "semver": {
                    "version": "5.5.1",
                    "from": "semver@5.5.1",
                    "resolved": "https://registry.npmjs.org/semver/-/semver-5.5.1.tgz"
                }
            }
        },
        "revalidator": {
            "version": "0.3.1",
            "from": "revalidator@^0.3.1",
            "resolved": "https://registry.npmjs.org/revalidator/-/revalidator-0.3.1.tgz"
        },
        "semver": {
            "version": "5.5.1",
            "from": "semver@5.5.1",
            "resolved": "https://registry.npmjs.org/semver/-/semver-5.5.1.tgz"
        }
    }
}


def test_create_repo_and_generate_files():
    """Test create_repo_and_generate_files function."""
    giturl = "https://github.com/heroku/node-js-sample"
    access = {
        "access_token": "blahblah"
    }
    instance = go.GitOperationTask.create_test_instance()
    manifests = instance.create_repo_and_generate_files(giturl,
                                                        "npm",
                                                        access)
    assert len(manifests) == 1
    assert manifests[0].filename == "npmlist.json"

    giturl = "https://github.com/jitpack/maven-simple"
    manifests = instance.create_repo_and_generate_files(giturl,
                                                        "maven",
                                                        access)
    assert len(manifests) == 1
    assert "dependencies.txt" in manifests[0].filename
