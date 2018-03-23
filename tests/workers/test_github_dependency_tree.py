"""Test GithubDependencyTreeTask."""

import pytest

from f8a_worker.workers import GithubDependencyTreeTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestGithubDependencyTreeTask(object):
    """Test GithubDependencyTreeTask."""

    def test_maven_index_checker_repo(self):
        """Test GithubDependencyTreeTask."""
        args = {'github_repo': 'https://github.com/fabric8-analytics/maven-index-checker.git',
                'github_sha': 'de64e1534724e53766dda472e9418350b85a1521',
                'email_ids': 'dummy'}
        task = GithubDependencyTreeTask.create_test_instance(task_name='dependency_tree')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'dependencies', 'github_repo', 'github_sha', 'email_ids'}
        obtained_dependencies = set(results['dependencies'])
        expected_direct_dependencies = {'com.googlecode.json-simple:json-simple:1.1.1',
                                        'org.apache.maven.indexer:indexer-core:6.0.0'}
        assert expected_direct_dependencies.issubset(obtained_dependencies)
        expected_transitive_dependencies = {'commons-io:commons-io:2.0.1',
                                            'com.google.guava:guava:20.0',
                                            'junit:junit:4.10'}
        assert expected_transitive_dependencies.issubset(obtained_dependencies)
