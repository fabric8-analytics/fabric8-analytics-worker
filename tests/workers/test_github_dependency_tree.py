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

    @pytest.mark.usefixtures("pypi")
    def test_python_requirements_txt(self):
        """Test python repository with requirements.txt."""
        args = {
            "github_repo": "https://github.com/abs51295/status-api",
            "github_sha": "229f47d3a634ae6a6e660228c7ceaeb70bb4cfaa",
            "email_ids": "dummy"
        }
        task = GithubDependencyTreeTask.create_test_instance(task_name='dependency_tree')
        results = task.execute(args)
        assert isinstance(results, dict)
        assert set(results.keys()) == {'dependencies', 'github_repo', 'github_sha', 'email_ids'}
        obtained_dependencies = set(results['dependencies'])
        expected_dependencies = {'pypi:py-zabbix:1.1.0', 'pypi:uwsgi:2.0.15',
                                 'pypi:werkzeug:0.14.1', 'pypi:jinja2:2.10',
                                 'pypi:flask:0.12.1', 'pypi:click:6.7',
                                 'pypi:six:1.11.0', 'pypi:aniso8601:3.0.0',
                                 'pypi:itsdangerous:0.24', 'pypi:markupsafe:1.0',
                                 'pypi:flask-restful:0.3.5', 'pypi:pytz:2018.4'}

        assert obtained_dependencies == expected_dependencies

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

    def test_repo_with_no_lockfile(self):
        """Test repository with no lock file present."""
        args = {'github_repo': 'https://github.com/abs51295/code2vec',
                'github_sha': '02ec2d941f8dd1a26c1469aaaf4849a3a803423b',
                'email_ids': 'dummy'}
        task = GithubDependencyTreeTask.create_test_instance(task_name='dependency_tree')
        results = task.execute(args)

        assert isinstance(results, dict)
        assert set(results.keys()) == {'dependencies', 'github_repo', 'github_sha',
                                       'email_ids', 'lock_file_absent', 'message'}

        obtained_dependencies = set(results['dependencies'])
        assert obtained_dependencies == set()
        lock_file_absent = results['lock_file_absent']
        assert lock_file_absent is True
