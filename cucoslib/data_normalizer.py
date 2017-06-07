#!/usr/bin/python3
"""
Extracts ecosystem specific information and transforms it to a common scheme

Scans the cache path for manifest files (package.json, setup.py, *.gemspec, *.jar, Makefile etc.) to extract meta data and transform it a common scheme.

Output: information such as: homepage, bug tracking, dependencies

sample output:
{'author': 'Aaron Patterson <aaronp@rubyforge.org>, Mike Dalessio '
           '<mike.dalessio@gmail.com>, Yoko Harada <yokolet@gmail.com>',
 'declared_license': 'MIT',
 'dependencies': ['mini_portile2 ~>2.0.0.rc2'],
 'description': 'Nokogiri is an HTML, XML, SAX, and Reader parser.',
 'devel_dependencies': ['rdoc ~>4.0',
                        'hoe-bundler >=1.1',
                        'hoe-debugging ~>1.2.1',
                        'hoe ~>3.14'],
 'homepage': 'http://nokogiri.org',
 'name': 'nokogiri',
 'version': '1.6.7.2'}
"""

import sys
import argparse
import json
from os import path
from itertools import zip_longest

from cucoslib.utils import parse_gh_repo


# TODO: we need to unify the output from different ecosystems
class DataNormalizer(object):
    description = 'Collects `Release` specific information from Mercator'

    @staticmethod
    def transform_keys(data, keymap):
        """
         Collect known keys and/or rename existing keys
        :param data: dictionary, mercator output
        :param keymap: n-tuple of 2-tuples
            each 2-tuple can have one of these forms:
            ('a',) - get 'a'
            ('b', 'c',) - get 'b' and rename it to 'c'
            (('d', 'e',),) - get 'd' or 'e'
            (('f', 'g',), 'h') - get 'f' or 'g' and rename it to 'h'
        :return: dictionary with keys from keymap only
        """
        out = {}
        value = None
        for pair in keymap:
            in_key = pair[0]
            if not isinstance(in_key, tuple):
                value = data.get(in_key, None)
            else:  # e.g. ('license', 'licenses',)
                for in_k in in_key:
                    value = data.get(in_k, None)
                    if value is not None:
                        break
                in_key = in_k
            key = in_key if len(pair) == 1 else pair[1]
            out[key] = value

        return out

    @staticmethod
    def _join_name_email(name_email_dict, name_key='name', email_key='email'):
        """ # {'name':'A', 'email':'B@C.com'} -> 'A <B@C.com>' """

        if not isinstance(name_email_dict, dict):
            return name_email_dict

        name_email_str = name_email_dict.get(name_key, '')
        if email_key in name_email_dict:
            if name_email_str:
                name_email_str += ' '
            name_email_str += '<' + name_email_dict[email_key] + '>'
        return name_email_str

    @staticmethod
    def _are_tests_implemented(data):
        """
        Say whether a package implements tests based on metadata info only isn't much reliable,
        but we have some indicators.
        """
        # NPM - package.json: metadata can contain 'scripts'.'test'
        if 'scripts' in data:  # added by _handle_javascript()
            if data['scripts'] is None:
                return False
            else:
                test_script = data.get('scripts', {}).get('test', '')
                # Existing test_script doesn't say much about whether it really runs some tests.
                # For example: 'npm init' uses 'echo "Error: no test specified" && exit 1'
                # as a default value of 'scripts'.'test'
                return test_script != '' and 'Error: no test specified' not in test_script

        # Python: metadata can contain 'test_requires'/'tests_require'.
        # Even it doesn't say anything about whether there really are any tests implemented,
        # it is an indicator.
        #
        # "tests_require" can be found in setup.py
        if data.get('tests_require'):
            return True
        # "test_requires" can be found in *.dist-info/metadata.json
        try:
            # "test_requires": [{"requires": ["pytest (>=2.5.2)"]}], "version": "1.7.5"}
            test_requires = data['test_requires'][0]['requires']
            return len(test_requires) > 0
        except Exception:
            pass
        return False

    def _handle_javascript(self, data):
        "Handle Javascript package (package.json) analysis data"
        key_map = ((('license', 'licenses',), 'declared_license'),
                   ('_dependency_tree_lock_file', '_dependency_tree_lock'), ('homepage',), ('version',),
                   ('description',), ('dependencies',), ('devDependencies', 'devel_dependencies'),
                   ('bugs', 'bug_reporting'), ('author',), ('contributors',), ('maintainers',),
                   ('repository', 'code_repository'), ('name',),
                   (('engine', 'engines'), 'engines'), ('gitHead', 'git_head'), ('readme',),
                   ('scripts',), ('files',), ('keywords',))

        base = self.transform_keys(data, key_map)

        # {'url': 'https://github.com/o/p/issues',
        #  'email': 'project@name.com'} -> 'https://github.com/o/p/issues <project@name.com>'
        if 'bug_reporting' in base and isinstance(base['bug_reporting'], dict):
            base['bug_reporting'] = self._join_name_email(base['bug_reporting'], 'url')
        if 'author' in base and isinstance(base['author'], dict):
            base['author'] = self._join_name_email(base['author'])
        if 'contributors' in base and isinstance(base['contributors'], list):
            base['contributors'] = [self._join_name_email(m) for m in base['contributors']]
        if 'maintainers' in base and isinstance(base['maintainers'], list):
            base['maintainers'] = [self._join_name_email(m) for m in base['maintainers']]

        # 'a/b' -> {'type': 'git', 'url': 'https://github.com/a/b.git'}
        if 'code_repository' in base and isinstance(base['code_repository'], str):
            k = 'code_repository'
            url = base[k]
            if url.count('/') == 1:  # e.g. 'expressjs/express'
                if ':' in url:
                    if url.startswith('bitbucket:'):
                        owner, repo = url[len('bitbucket:'):].split('/')
                        url = 'https://{owner}@bitbucket.org/{owner}/{repo}.git'.format(
                            owner=owner, repo=repo)
                    if url.startswith('gitlab:'):
                        url = 'https://gitlab.com/' + url[len('gitlab:'):] + '.git'
                else:  # default is github
                    url = 'https://github.com/' + url + '.git'
            repository_dict = {'type': 'git', 'url': url}
            #self.log.debug("transforming '%s' to '%s'" % (base[k], repository_dict))
            base[k] = repository_dict

        # transform a dict/list (deprecated, but still used in older packages) to string
        if 'declared_license' in base and not isinstance(base['declared_license'], str):
            k = 'declared_license'
            value = base[k]
            # e.g. {"license": {"type": "ISC", "url": "http://opensource.org/licenses/ISC"}}
            if isinstance(value, dict) and \
               "type" in value and isinstance(value["type"], str):
                base[k] = value["type"]
            # e.g. {"licenses": [{"type": "MIT", "url": "http://..."},
            #                    {"type": "Apache-2.0", "url": "http://..."}]}
            elif isinstance(value, list):
                licenses = []
                for l in value:
                    if isinstance(l, dict) and \
                       "type" in l and isinstance(l["type"], str):
                        licenses.append(l["type"])
                base[k] = ", ".join(licenses)

        # transform dict dependencies into flat list of strings
        # name and version spec are separated by ' ' space
        for dep_section in ('dependencies', 'devel_dependencies'):
            # the "is not None" part is important, since we also want to translate empty dict
            #   to empty list
            if dep_section in base and base[dep_section] is not None:
                flat_deps = []
                for name, spec in base[dep_section].items():
                    flat_deps.append('{} {}'.format(name, spec))
                base[dep_section] = flat_deps

        engines = base['engines']
        # example: request@2.16.6: {"engines":["node >= 0.8.0"]}
        if isinstance(engines, list):
            base['engines'] = {}
            for engine in engines:
                # ["node >= 0.8.0"]  ->  {"node": ">=0.8.0"}
                name, operator, version = engine.split()
                base['engines'][name] = operator + version
        if base['engines'] is not None:
            for name, version_spec in base['engines'].items():
                if ' ' in version_spec:
                    # ">= 0.8.0"  ~>  ">=0.8.0"
                    base['engines'][name] = version_spec.replace(' ', '')

        def _process_level(level, collect):
            "Process a `level` of dependency tree and store data in `collect`"
            for name, data in level.items():
                deps = []
                item = {
                    'name': name,
                    'version': data.get('version', ''),
                    'specification': data.get('from', None),
                    'resolved': data.get('resolved', None),
                    'dependencies': deps
                }
                collect.append(item)
                _process_level(data.get('dependencies', {}), deps)

        lockfile = base.get('_dependency_tree_lock')
        if lockfile is not None:
            dependencies = []
            _process_level(lockfile.get('dependencies', {}), dependencies)
            lockfile['version'] = lockfile.pop('npm-shrinkwrap-version', None)
            lockfile['runtime'] = data.get('_nodeVersion', "")
            lockfile['dependencies'] = dependencies
            lockfile.pop('node-version', None)

        base['_tests_implemented'] = self._are_tests_implemented(base)
        return base

    def _python_identify_repo(self, homepage):
        """Returns code repository dict filled with homepage, if homepage is GH repo
        (None otherwise)
        """
        if parse_gh_repo(homepage):
            return {'url': homepage, 'type': 'git'}
        return None

    def _python_split_keywords(self, keywords):
        if isinstance(keywords, list):
            return keywords
        keywords = keywords.split(',')
        keywords = [kw.strip() for kw in keywords]
        return keywords

    def _handle_python(self, data):
        "Handle Python package (setup.py) analysis data"
        key_map = (('license', 'declared_license'), ('url', 'homepage'),
                   ('install_requires', 'dependencies'), ('name',),
                   ('description',), ('version',))

        transformed = self.transform_keys(data, key_map)
        transformed['author'] = self._join_name_email(data, 'author', 'author_email')
        transformed['code_repository'] = self._python_identify_repo(transformed.get('homepage', ''))
        transformed['keywords'] = self._python_split_keywords(data.get('keywords', []))
        return transformed

    def _handle_python_dist(self, data):
        details = data.get('extensions', {}).get('python.details', None)
        result = None
        if details is not None:
            contacts = details.get('contacts', [])
            urls = details.get('project_urls', {})
            # https://www.python.org/dev/peps/pep-0426/#mapping-dependencies-to-development-and-distribution-activities
            #  says that in runtime, this package will need both run_requires and meta_requires
            requires = data.get('run_requires', []) + data.get('meta_requires', [])
            dependencies = []
            for rlist in [r.get('requires', []) for r in requires]:
                dependencies.extend(rlist)

            author = None
            for contact in contacts:
                if contact.get('role', '') == 'author':
                    author = self._join_name_email(contact)
            homepage = None
            for k, v in urls.items():
                if k.lower() == 'home':
                    homepage = v
            result = {'author': author, 'homepage': homepage, 'description': data.get('summary', None),
                      'dependencies': sorted(dependencies), 'name': data.get('name', None),
                      'version': data.get('version', None),
                      'declared_license': details.get('license', None)}
        else:
            key_map = (('summary', 'description'), ('requires_dist', 'dependencies'), ('name',),
                       ('home-page', 'homepage'), ('version',), ('license', 'declared_license'),
                       ('platform',), )

            result = self.transform_keys(data, key_map)
            result['author'] = self._join_name_email(data, 'author', 'author-email')
        result['code_repository'] = self._python_identify_repo(result.get('homepage') or '')
        result['keywords'] = self._python_split_keywords(data.get('keywords', []))
        return result

    def _handle_java(self, data):
        # we expect pom.xml to be there, since it's always downloaded to top level by InitTask
        pom = data.get('pom.xml')
        key_map = (('name',), ('version', ), ('description', ), ('url', 'homepage'))
        # handle licenses
        transformed = self.transform_keys(pom, key_map)
        transformed['declared_license'] = ', '.join(pom.get('licenses', [])) or None
        # dependencies with scope 'compile' and 'runtime' are needed at runtime;
        # dependencies with scope 'provided' are not necessarily runtime dependencies,
        # but they are commonly used for example in web applications
        dependencies_dict = pom.get('dependencies', {}).get('compile', {})
        dependencies_dict.update(pom.get('dependencies', {}).get('runtime', {}))
        dependencies_dict.update(pom.get('dependencies', {}).get('provided', {}))
        # dependencies with scope 'test' are only needed for testing;
        dev_dependencies_dict = pom.get('dependencies', {}).get('test', {})

        transformed['dependencies'] = [k.rstrip(':') + ' ' + v for k, v in dependencies_dict.items()]
        transformed['devel_dependencies'] = [k.rstrip(':') + ' ' + v for k, v in dev_dependencies_dict.items()]
        # handle code_repository
        if 'scm_url' in pom:
            # TODO: there's no way we can tell 100 % what the type is, but we could
            #  try to handle at least some cases, e.g. github will always be git etc
            transformed['code_repository'] = {'url': pom['scm_url'], 'type': 'unknown'}
        return transformed

    @staticmethod
    def _extract_engine_requirements(data, key):
        # This is what mercator creates when parsing rubygems metadata.yaml
        # key is for example 'required_rubygem_version'
        # key: {
        #      "requirements": [
        #        [">=", {"version": "1.9.2"}]
        #      ]
        #    }
        # extract just the ">=1.9.2" from it
        try:
            requirement = data[key]['requirements'][0]
            return requirement[0] + requirement[1]['version']
        except Exception:
            return None

    def _handle_rubygems(self, data):
        key_map = (('author',), ('authors',), ('email',), ('name',), ('version',), ('homepage',),
                   (('license', 'licenses',), 'declared_license'),
                   ('dependencies',), ('devel_dependencies',), ('description',),
                   ('metadata',), ('platform',), )
        transformed = self.transform_keys(data, key_map)

        # list of licenses  ->  string of comma separated licenses
        value = transformed['declared_license']
        if isinstance(value, list):
            transformed['declared_license'] = ", ".join(value)

        # 'authors' (list of strings) or 'author' (string) is required attribute
        authors = transformed.get('authors') or [transformed.get('author')]
        transformed.pop('authors')   # we don't want this one
        emails = []
        if transformed.get('email'):
            # 'email' can also be either a list or string
            if isinstance(transformed['email'], list):
                emails = transformed['email']
            else:
                emails = [transformed['email']]
        transformed.pop('email')  # we don't want this one
        # zip email(s) with author(s)
        authors_ = []
        for author, email in zip_longest(authors, emails, fillvalue=''):
            if email:
                authors_.append(author + ' <' + email + '>')
            else:
                authors_.append(author)
        transformed['author'] = ", ".join(authors_)

        # 'description' is optional attribute, while 'summary' is required
        if not transformed['description'] and data.get('summary'):
            transformed['description'] = data['summary']

        # 'version': {'version': '4.8.4'}  ->  'version': '4.8.4'
        if 'version' in transformed and isinstance(transformed['version'], dict):
            transformed['version'] = transformed['version'].get('version', '')

        # transform
        # [{"name": "charlock_holmes",
        #    "prerelease": false,
        #    "type": ":runtime",
        #    "requirement": {"requirements": [["~>", {"version": "0.7.3"}]]},
        #    "version_requirements": {"requirements": [["~>", {"version": "0.7.3"}]]}}]
        # to ["charlock_holmes ~>0.7.3"]
        if 'dependencies' in transformed and transformed['dependencies']:
            rt_deps = []
            dev_deps = []
            for dep in transformed['dependencies']:
                tmp = dep.split(' ')
                name = tmp[0]
                operator = tmp[1].replace('(', '')
                version = tmp[2].replace(')', '')
                flat_dep = '{} {}{}'.format(name, operator, version)
                # if it's marked as runtime or there is no flag
                if 'runtime' in tmp or len(tmp) == 3:
                    rt_deps.append(flat_dep)
                elif 'development)' in tmp:
                    dev_deps.append(flat_dep)
            transformed['dependencies'] = rt_deps  # runtime dependencies
            transformed['devel_dependencies'] = dev_deps  # development dependencies
        return transformed

    def handle_data(self, data, keep_path=False):
        def _passthrough(unused):
            #log.debug('ecosystem %s not handled', data['ecosystem'])
            pass

        "Arbitrate between various build/packaging systems"
        # TODO: some fallback if ecosystem is not matched
        switch = {'python': self._handle_python,
                  'python-dist': self._handle_python_dist,
                  'python-requirementstxt': self._handle_python_dist,
                  'npm': self._handle_javascript,
                  'java-pom': self._handle_java,
                  'ruby': self._handle_rubygems}

        result = switch.get(data['ecosystem'].lower(), _passthrough)(data.get('result', {}))
        if result is None:
            result = {}

        if keep_path:
            result['path'] = data.get('path', None)
        result['ecosystem'] = data['ecosystem'].lower()
        return result

    @staticmethod
    def get_outermost_items(list_):
        "Sort by the depth of the path so the outermost come first"
        sorted_list = sorted(list_, key=lambda a: len(a['path'].split(path.sep)))
        if sorted_list:
            outermost_len = len(sorted_list[0]['path'].split(path.sep))
            sorted_list = [i for i in sorted_list if
                           len(i['path'].split(path.sep)) == outermost_len]
        return sorted_list

    @staticmethod
    def _sanitize_data(data):
        # make sure deps are never 'null'
        if 'dependencies' in data and data['dependencies'] is None:
            data['dependencies'] = []
        if 'devel_dependencies' in data and data['devel_dependencies'] is None:
            data['devel_dependencies'] = []

        return data

    @staticmethod
    def _dict2json(o, pretty=True):
        kwargs = {}
        if pretty:
            kwargs['sort_keys'] = True,
            kwargs['separators'] = (',', ': ')
            kwargs['indent'] = 2

        return json.dumps(o, **kwargs)

    def main(self):
        parser = argparse.ArgumentParser(sys.argv[0],
                                         description='Data normalizer for mercator')
        parser.add_argument('--restricted', dest='restricted', action='store_true',
                            help='remove parts that could carry privacy information')
        parser.add_argument('--no-pretty', dest='no_pretty', action='store_true',
                            help='do not print nicely formatted JSON')
        args = parser.parse_args()

        content = json.load(sys.stdin)

        if content:
            items = content.get('items') or []
            for item in items:
                item['result'] = self.handle_data(item)

        if args.restricted and content:
            items = content.get('items') or []
            for item in items:
                p = item.pop('path')
                if p:
                    item['path_depth'] = p.count(path.sep)

                keys = (('version',),
                        ('name',),
                        ('dependencies',),
                        ('devel_dependencies',),
                        ('_dependency_tree_lock_file',))
                item['result'] = self.transform_keys(item.get('result', {}), keys)

        print(self._dict2json(content, pretty=not args.no_pretty))

        return 0


if __name__ == "__main__":
    sys.exit(DataNormalizer().main())
