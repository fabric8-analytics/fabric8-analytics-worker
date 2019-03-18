"""Tests for JavaScript data normalizers."""

import pytest
from f8a_worker.data_normalizer import NpmDataNormalizer


@pytest.mark.parametrize('data, expected', [
    ({'author': {'name': 'Santa Claus', 'email': 'santa@SantaClaus.com', 'url': 'north'}},
     {'author': 'Santa Claus <santa@SantaClaus.com>'}),
    ({'author': {}},
     {'author': None}),
    ({'author': ()},
     {'author': None}),
    ({'contributors': [{'email': 'mscdex@mscdex.net', 'name': 'mscdex', 'url': 'there'},
                       {'email': 'fishrock123@rocketmail.com', 'name': 'fishrock123'}]},
     {'contributors': ['mscdex <mscdex@mscdex.net>',
                       'fishrock123 <fishrock123@rocketmail.com>']}),
    ({'maintainers': [{'email': 'mscdex@mscdex.net', 'name': 'mscdex', 'url': 'there'},
                      {'email': 'fishrock123@rocketmail.com', 'name': 'fishrock123'}]},
     {'maintainers': ['mscdex <mscdex@mscdex.net>',
                      'fishrock123 <fishrock123@rocketmail.com>']}),
    ({'bugs': {'url': 'https://github.com/owner/project/issues', 'email': 'project@name.com'}},
     {'bug_reporting': 'https://github.com/owner/project/issues <project@name.com>'}),
    ({'bugs': [{'url': 'https://github.com/owner/project/issues', 'email': 'project@name.com'}]},
     {'bug_reporting': None}),
    ({'license': 'BSD-3-Clause'},
     {'declared_licenses': ['BSD-3-Clause']}),
    ({'license': ''},
     {'declared_licenses': None}),
    ({'license': None},
     {'declared_licenses': None}),
    ({'license': '(ISC OR GPL-3.0)'},
     {'declared_licenses': ['ISC', 'GPL-3.0']}),
    # deprecated, but used in older packages
    ({'license': {'type': 'ISC',
                  'url': 'http://opensource.org/licenses/ISC'}},
     {'declared_licenses': ['ISC']}),
    # deprecated, but used in older packages
    ({'licenses': [{'type': 'MIT',
                    'url': 'http://www.opensource.org/licenses/mit-license.php'},
                   {'type': 'Apache-2.0',
                    'url': 'http://opensource.org/licenses/apache2.0.php'}]},
     {'declared_licenses': ['MIT', 'Apache-2.0']}),
    ({'repository': {'type': 'git', 'url': 'https://github.com/npm/npm.git'}},
     {'code_repository': {'type': 'git', 'url': 'https://github.com/npm/npm.git'}}),
    ({'repository': 'expressjs/express'},
     {'code_repository': {'type': 'git', 'url': 'https://github.com/expressjs/express.git'}}),
    ({'repository': 'bitbucket:exmpl/repo'},
     {'code_repository': {'type': 'git', 'url': 'https://exmpl@bitbucket.org/exmpl/repo.git'}}),
    ({'repository': 'gitlab:another/repo'},
     {'code_repository': {'type': 'git', 'url': 'https://gitlab.com/another/repo.git'}}),
    ({'dependencies': {"escape-html": "1.0.1"}},
     {'dependencies': ["escape-html 1.0.1"]}),
    ({'description': 'More NPM'},
     {'description': 'More NPM'}),
    ({'description': ['More', 'NPM']},
     {'description': 'More NPM'}),
    ({'description': ('More', 'NPM')},
     {'description': 'More NPM'}),
    ({'description': None},
     {'description': None}),
    ({'description': {}},
     {'description': '{}'}),
    ({'devDependencies': {'mocha': '~2.0.0'}},
     {'devel_dependencies': ['mocha ~2.0.0']}),
    ({'author': {'name': 'Santa Claus', 'email': 'santa@SantaClaus.com'}, 'engines': '8.6'},
     {'author': 'Santa Claus <santa@SantaClaus.com>', 'engines': {}}),
])
def test_transforming_javascript_data(data, expected):
    """Test normalizing of npm package metadata."""
    transformed_data = NpmDataNormalizer(data).normalize()
    for key, value in expected.items():
        assert key in transformed_data
        assert transformed_data[key] == value


@pytest.mark.parametrize('data,expected', [
    ({}, False),
    # package.json (nodejs), no 'scripts'
    ({"scripts": None}, False),
    # package.json (nodejs), missing "test"
    ({"scripts": {"docs": "jsdoc2md -t ..."}}, False),
    # package.json, default 'npm init' test script
    ({"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}, False),
    # package.json, ok
    ({"scripts": {"test": "tape test/*.js", "docs": "jsdoc2md -t"}}, True)
])
def test__are_tests_implemented(data, expected):
    """Test NpmDataNormalizer._are_tests_implemented()."""
    dn = NpmDataNormalizer(data)
    assert dn._are_tests_implemented() == expected
