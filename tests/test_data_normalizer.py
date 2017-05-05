from io import open
import json
import os
import pytest
from os import path

from cucoslib.data_normalizer import DataNormalizer


def compare_dictionaries(a, b):
    def mapper(item):
        if isinstance(item, list):
            return frozenset(map(mapper, item))
        if isinstance(item, dict):
            return frozenset({mapper(k): mapper(v) for k, v in item.items()}.items())
        return item

    return mapper(a) == mapper(b)


class TestDataNormalizer(object):
    def setup_method(self, method):
        self.data = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)), 'data', 'dataNormalizer')
        self._dataNormalizer = DataNormalizer()

    def _load_json(self, f):
        with open(os.path.join(self.data, f), encoding='utf-8') as f:
            return json.load(f)

    @pytest.mark.parametrize('args, expected', [
        # pick one key which IS there
        ({'data': {'author': 'me', 'version': '0.1.2'}, 'keymap': (('author',),)},
         {'author': 'me'}),
        # pick one key which IS NOT there
        ({'data': {'author-name': 'me', 'version': '0.1.2'}, 'keymap': (('author',),)},
         {'author': None}),
        # pick & and rename one key which IS there
        ({'data': {'author-name': 'me'}, 'keymap': (('author-name', 'author',),)},
         {'author': 'me'}),
        # pick & and rename one key which IS NOT there
        ({'data': {'authors': 'they'}, 'keymap': (('author-name', 'author',),)},
         {'author': None}),
        # pick one of keys
        ({'data': {'license': 'MIT'}, 'keymap': ((('license', 'licenses',), ),)},
         {'license': 'MIT'}),
        # pick one of keys
        ({'data': {'licenses': ['MIT', 'BSD']}, 'keymap': ((('license', 'licenses',),),)},
         {'licenses': ['MIT', 'BSD']}),
        # pick one of keys and rename it
        ({'data': {'license': 'MIT'}, 'keymap': ((('license', 'licenses',), 'declared_license'),)},
         {'declared_license': 'MIT'}),
    ])
    def test__transform_keys(self, args, expected):
        assert self._dataNormalizer.transform_keys(**args) == expected

    @pytest.mark.parametrize('args, expected', [
        ({'name_email_dict': {'name': 'A', 'email': 'B@C.com'}},
         "A <B@C.com>"),
        ({'name_email_dict': {'name': 'A'}},
         "A"),
        ({'name_email_dict': {'email': 'B@C.com'}},
         "<B@C.com>"),
        ({'name_email_dict': {'author': 'A', 'author-email': 'B@C.com'}, 'name_key': 'author', 'email_key': 'author-email'},
         "A <B@C.com>"),
        ({'name_email_dict': {'url': 'https://github.com/o/p/issues', 'email': 'project@name.com'}, 'name_key': 'url'},
         "https://github.com/o/p/issues <project@name.com>"),
    ])
    def test__join_name_email(self, args, expected):
        assert self._dataNormalizer._join_name_email(**args) == expected

    @pytest.mark.parametrize('args, expected', [
        ({'data': {}},
         False),
        # package.json (nodejs), no 'scripts'
        ({'data': {"scripts": None}},
         False),
        # package.json (nodejs), missing "test"
        ({'data': {"scripts": {"docs": "jsdoc2md -t ..."}}},
         False),
        # package.json, default 'npm init' test script
        ({'data': {"scripts": {"test": "echo \"Error: no test specified\" && exit 1"}}},
         False),
        # package.json, ok
        ({'data': {"scripts": {"test": "tape test/*.js", "docs": "jsdoc2md -t"}}},
         True),
        # setup.py, ok
        ({'data': {'tests_require': ['mock']}},
         True),
        # metadata.json (Python)
        ({'data': {"test_requires": [{"requires": ["mock (==1.0.1)", "pytest (==2.9.1)"]}]}},
         True),
    ])
    def test__are_tests_implemented(self, args, expected):
        assert self._dataNormalizer._are_tests_implemented(**args) == expected

    def test_transforming_setup_py(self):
        data = self._load_json('setup-py-from-mercator')
        expected = self._load_json('setup-py-expected')
        assert self._dataNormalizer.handle_data(data['items'][0]) == expected

    def test_transforming_pkginfo(self):
        data = self._load_json('PKG-INFO-from-mercator')
        expected = self._load_json('PKG-INFO-expected')
        assert self._dataNormalizer.handle_data(data['items'][0]) == expected

    def test_transforming_metadata_json(self):
        data = self._load_json('metadata-json-from-mercator')
        expected = self._load_json('metadata-json-expected')
        assert self._dataNormalizer.handle_data(data['items'][0]) == expected

    def test_transforming_rubygems_metadata_yaml(self):
        data = self._load_json('rubygems-metadata-json-from-mercator')
        expected = self._load_json('rubygems-metadata-json-expected')
        assert self._dataNormalizer.handle_data(data['items'][0]) == expected

    @pytest.mark.parametrize('args, expected', [
        # correct
        ({'data': {'required_rubygem_version': {"requirements": [[">=", {"version": "1.9.2"}]]}}, 'key': 'required_rubygem_version'},
         '>=1.9.2'),
        # bad
        ({'data': {'required_ruby_version': {"requirement": [[">=", {"version": "1.9.2"}]]}},
          'key': 'required_ruby_version'},
         None),
        # bad
        ({'data': {'required_ruby_version': {"requirements": [[{"version": "1.9.2"}, ">="]]}},
          'key': 'required_ruby_version'},
         None),
    ])
    def test__extract_engine_requirements(self, args, expected):
        assert self._dataNormalizer._extract_engine_requirements(**args) == expected

    @pytest.mark.parametrize('data, expected', [
        ({'author': {'name': 'Santa Claus', 'email': 'santa@SantaClaus.com', 'url': 'north'}},
         {'author': 'Santa Claus <santa@SantaClaus.com>'}),
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
        ({'license': 'BSD-3-Clause'},
         {'declared_license': 'BSD-3-Clause'}),
        ({'license': '(ISC OR GPL-3.0)'},
         {'declared_license': '(ISC OR GPL-3.0)'}),
        # deprecated, but used in older packages
        ({'license': {'type': 'ISC',
                      'url': 'http://opensource.org/licenses/ISC'}},
         {'declared_license': 'ISC'}),
        # deprecated, but used in older packages
        ({'licenses': [{'type': 'MIT',
                        'url': 'http://www.opensource.org/licenses/mit-license.php'},
                       {'type': 'Apache-2.0',
                        'url': 'http://opensource.org/licenses/apache2.0.php'}]},
         {'declared_license': 'MIT, Apache-2.0'}),
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
        ({'devDependencies': {'mocha': '~2.0.0'}},
         {'devel_dependencies': ['mocha ~2.0.0']}),
    ])
    def test_transforming_javascript_data(self, data, expected):
        transformed_data = self._dataNormalizer._handle_javascript(data)
        for key, value in expected.items():
            assert key in transformed_data
            assert transformed_data[key] == value

    def test_transforming_npm_shrinkwrap_data(self):
        data = self._load_json('npm-with-shrinkwrap-json-from-mercator')
        expected = self._load_json('npm-with-shrinkwrap-json-expected')
        assert compare_dictionaries(self._dataNormalizer.handle_data(data), expected)

    @pytest.mark.parametrize('transformed_data, expected', [
        ({'dependencies': ["escape-html 1.0.1"]},
         {'dependencies': ["escape-html 1.0.1"]}),
        ({'dependencies': None},
         {'dependencies': []}),
        ({'devel_dependencies': ['mocha ~2.0.0']},
         {'devel_dependencies': ['mocha ~2.0.0']}),
        ({'devel_dependencies': None},
         {'devel_dependencies': []}),
    ])
    def test_sanitizing_data(self, transformed_data, expected):
        sanitized_data = self._dataNormalizer._sanitize_data(transformed_data)
        for key, value in expected.items():
            assert key in sanitized_data
            assert sanitized_data[key] == value

    def sort_by_path(self, dict_):
        return sorted(dict_, key=lambda a: len(a['path'].split(path.sep)))

    def test_get_outermost_items(self):
        d = [{'path': '/a/b/c/d'}, {'path': '/a/b/c'}, {'path': '/a'}]
        assert self._dataNormalizer.get_outermost_items(d) == [{'path': '/a'}]

        d = [{'path': 'bbb'}, {'path': 'a/b/c/'}]
        assert self._dataNormalizer.get_outermost_items(d) == [{'path': 'bbb'}]

        d = [{'path': '/a/b'}, {'path': '/b/c'}, {'path': '/c/d/e'}]
        expected = self.sort_by_path([{'path': '/a/b'}, {'path': '/b/c'}])
        result = self.sort_by_path(self._dataNormalizer.get_outermost_items(d))
        assert len(result) == len(expected)
        for i in range(len(expected)):
            assert compare_dictionaries(result[i], expected[i]) == True

    @pytest.mark.parametrize('data, expected', [
        ({'pom.xml': {'dependencies': {'compile': {'g:a::': '1.0'}}}},
         {'dependencies': ['g:a 1.0']}),
        ({'pom.xml': {'dependencies': {'runtime': {'g:a::': '1.0'}}}},
         {'dependencies': ['g:a 1.0']}),
        ({'pom.xml': {'dependencies': {'provided': {'g:a::': '1.0'}}}},
         {'dependencies': ['g:a 1.0']}),
        ({'pom.xml': {'dependencies': {'test': {'g:a::': '1.0'}}}},
         {'devel_dependencies': ['g:a 1.0']}),
        ({'pom.xml': {'dependencies': {'compile': {'g:a::': '1.0', 'g2:a2::': '1.0.3-SNAPSHOT'},
                                       'test': {'t:t::': '0'},
                                       'runtime': {'r:r::': 'version'},
                                       'provided': {'p:p::': '1000'}}}},
         {'dependencies': sorted(['g:a 1.0', 'g2:a2 1.0.3-SNAPSHOT', 'r:r version', 'p:p 1000']),
          'devel_dependencies': sorted(['t:t 0'])}),
        ({'pom.xml': {'scm_url': 'git@github.com:fabric8-analytics/fabric8-analytics-worker.git'}},
         {'code_repository': {'url': 'git@github.com:fabric8-analytics/fabric8-analytics-worker.git', 'type': 'unknown'}}),
        ({'pom.xml': {'licenses': ['ASL 2.0', 'MIT']}},
         {'declared_license': 'ASL 2.0, MIT'}),
        ({'pom.xml': {'description': 'Ich bin ein Bayesianer'}},
         {'description': 'Ich bin ein Bayesianer'}),
        ({'pom.xml': {'url': 'https://github.com/fabric8-analytics/fabric8-analytics-worker'}},
         {'homepage': 'https://github.com/fabric8-analytics/fabric8-analytics-worker'}),
    ])
    def test_transforming_java_data(self, data, expected):
        transformed_data = self._dataNormalizer._handle_java(data)
        for key, value in expected.items():
            assert key in transformed_data
            transformed_value = sorted(transformed_data[key]) if isinstance(transformed_data[key], list) else transformed_data[key]
            assert transformed_value == value
