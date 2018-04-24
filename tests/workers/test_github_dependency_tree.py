"""Test GithubDependencyTreeTask."""

import pytest

from f8a_worker.workers import GithubDependencyTreeTask


@pytest.mark.usefixtures("dispatcher_setup")
class TestGithubDependencyTreeTask(object):
    """Test GithubDependencyTreeTask."""

    def test_maven_index_checker_repo(self):
        """Test maven repository with pom.xml."""
        args = {'github_repo': 'https://github.com/fabric8-analytics/maven-index-checker.git',
                'github_sha': 'de64e1534724e53766dda472e9418350b85a1521',
                'email_ids': 'dummy'}
        task = GithubDependencyTreeTask.create_test_instance(task_name='dependency_tree')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'dependencies', 'github_repo', 'github_sha', 'email_ids'}
        obtained_dependencies = set(results['dependencies'])
        expected_direct_dependencies = {'maven:com.googlecode.json-simple:json-simple:1.1.1',
                                        'maven:org.apache.maven.indexer:indexer-core:6.0.0'}
        assert expected_direct_dependencies.issubset(obtained_dependencies)
        expected_transitive_dependencies = {'maven:commons-io:commons-io:2.0.1',
                                            'maven:com.google.guava:guava:20.0',
                                            'maven:junit:junit:4.10'}
        assert expected_transitive_dependencies.issubset(obtained_dependencies)

    @pytest.mark.usefixtures("npm")
    def test_npm_repo_with_package_lock(self):
        """Test npm repository with package-lock.json."""
        args = {
            'github_repo': 'https://github.com/abs51295/node-js-sample',
            'github_sha': '01fe0580c697d34118baef3b9e5fe3edf64bc4e3',
            'email_ids': 'dummy'
        }
        task = GithubDependencyTreeTask.create_test_instance(task_name='dependency_tree')
        results = task.execute(args)
        assert isinstance(results, dict)
        assert set(results.keys()) == {'dependencies', 'github_repo', 'github_sha', 'email_ids'}
        obtained_dependencies = set(results['dependencies'])
        expected_dependencies = {'npm:express:4.16.3', 'npm:ipaddr.js:1.6.0',
                                 'npm:finalhandler:1.1.1', 'npm:inherits:2.0.3',
                                 'npm:content-disposition:0.5.2', 'npm:proxy-addr:2.0.3',
                                 'npm:ms:2.0.0', 'npm:etag:1.8.1',
                                 'npm:utils-merge:1.0.1', 'npm:qs:6.5.1',
                                 'npm:merge-descriptors:1.0.1',
                                 'npm:depd:1.1.1', 'npm:debug:2.6.9',
                                 'npm:cookie-signature:1.0.6',
                                 'npm:bytes:3.0.0', 'npm:mime-types:2.1.18',
                                 'npm:ee-first:1.1.1', 'npm:raw-body:2.3.2',
                                 'npm:setprototypeof:1.0.3', 'npm:parseurl:1.3.2',
                                 'npm:negotiator:0.6.1', 'npm:serve-static:1.13.2',
                                 'npm:path-to-regexp:0.1.7', 'npm:media-typer:0.3.0',
                                 'npm:iconv-lite:0.4.19', 'npm:setprototypeof:1.1.0',
                                 'npm:forwarded:0.1.2', 'npm:statuses:1.4.0',
                                 'npm:content-type:1.0.4', 'npm:fresh:0.5.2',
                                 'npm:array-flatten:1.1.1', 'npm:type-is:1.6.16',
                                 'npm:on-finished:2.3.0', 'npm:http-errors:1.6.2',
                                 'npm:accepts:1.3.5', 'npm:vary:1.1.2',
                                 'npm:unpipe:1.0.0', 'npm:safe-buffer:5.1.1',
                                 'npm:destroy:1.0.4', 'npm:encodeurl:1.0.2',
                                 'npm:mime-db:1.33.0', 'npm:body-parser:1.18.2',
                                 'npm:range-parser:1.2.0', 'npm:methods:1.1.2',
                                 'npm:send:0.16.2', 'npm:depd:1.1.2',
                                 'npm:cookie:0.3.1', 'npm:http-errors:1.6.3',
                                 'npm:mime:1.4.1', 'npm:escape-html:1.0.3'}

        assert obtained_dependencies == expected_dependencies
