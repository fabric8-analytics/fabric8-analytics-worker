#!/usr/bin/python3

"""
Code to transform data from Mercator [1] into a common scheme.

[1] https://github.com/fabric8-analytics/mercator-go
"""

import argparse
from itertools import zip_longest
import json
from os import path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

from f8a_worker.utils import parse_gh_repo


# TODO: we need to unify the output from different ecosystems

class DataNormalizer(object):
    """Transforms data from Mercator into a common scheme."""

    description = 'Collects `Release` specific information from Mercator'

    @staticmethod
    def transform_keys(data, keymap, lower=True):
        """Collect known keys and/or rename existing keys.

        :param data: dictionary, mercator output
        :param keymap: n-tuple of 2-tuples
            each 2-tuple can have one of these forms:
            ('a',) - get 'a'
            ('b', 'c',) - get 'b' and rename it to 'c'
            (('d', 'e',),) - get 'd' or 'e'
            (('f', 'g',), 'h') - get 'f' or 'g' and rename it to 'h'
        :param lower: bool, convert keys to lowercase
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
            if lower:
                key = key.lower()
            out[key] = value

        return out

    @staticmethod
    def _join_name_email(name_email_dict, name_key='name', email_key='email'):
        """Join name and email values into a string.

        # {'name':'A', 'email':'B@C.com'} -> 'A <B@C.com>'
        """
        if not isinstance(name_email_dict, dict):
            return name_email_dict

        name_email_str = name_email_dict.get(name_key) or ''
        if isinstance(name_email_dict.get(email_key), str):
            if name_email_str:
                name_email_str += ' '
            name_email_str += '<' + name_email_dict[email_key] + '>'
        return name_email_str

    @staticmethod
    def _are_tests_implemented(data):
        """Say whether a package implements tests.

        Metadata info only isn't much reliable, but we have some indicators.
        """
        # NPM - package.json: metadata can contain 'scripts'.'test'
        if 'scripts' in data:  # added by _handle_javascript()
            if data['scripts'] is None:
                return False
            else:
                test_script = data['scripts'].get('test', '')
                # Existing test_script doesn't say much about whether it really runs some tests.
                # For example: 'npm init' uses 'echo "Error: no test specified" && exit 1'
                # as a default value of 'scripts'.'test'
                return isinstance(test_script, str) and test_script != '' \
                    and 'Error: no test specified' not in test_script

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
        """Handle Javascript package (package.json) analysis data."""
        key_map = ((('license', 'licenses',), 'declared_licenses'),
                   ('_dependency_tree_lock_file', '_dependency_tree_lock'), ('homepage',),
                   ('version',),
                   ('description',), ('dependencies',), ('devDependencies', 'devel_dependencies'),
                   ('bugs', 'bug_reporting'), ('author',), ('contributors',), ('maintainers',),
                   ('repository', 'code_repository'), ('name',),
                   (('engine', 'engines'), 'engines'), ('gitHead', 'git_head'), ('readme',),
                   ('scripts',), ('files',), ('keywords',))

        def _rf(iterable):
            """Remove false/empty/None items from iterable."""
            return list(filter(None, iterable))

        base = self.transform_keys(data, key_map)

        # {'url': 'https://github.com/o/p/issues',
        #  'email': 'project@name.com'} -> 'https://github.com/o/p/issues <project@name.com>'
        if isinstance(base.get('bug_reporting'), dict):
            base['bug_reporting'] = self._join_name_email(base['bug_reporting'], 'url')
        if base.get('author'):
            if isinstance(base.get('author'), dict):
                base['author'] = self._join_name_email(base['author'])
            elif isinstance(base.get('author'), list):
                # Process it even it violates https://docs.npmjs.com/files/package.json
                if isinstance(base['author'][0], dict):
                    base['author'] = self._join_name_email(base['author'][0])
                elif isinstance(base['author'][0], str):
                    base['author'] = base['author'][0]
        if base['contributors'] is not None:
            if isinstance(base['contributors'], list):
                base['contributors'] = _rf(self._join_name_email(m) for m in base['contributors'])
            elif isinstance(base['contributors'], dict):
                base['contributors'] = _rf([self._join_name_email(base['contributors'])])
            elif isinstance(base['contributors'], str):
                base['contributors'] = _rf([base['contributors']])
        if isinstance(base.get('maintainers'), list):
            base['maintainers'] = _rf(self._join_name_email(m) for m in base['maintainers'])

        k = 'code_repository'
        if base[k]:
            # 'a/b' -> {'type': 'git', 'url': 'https://github.com/a/b.git'}
            if isinstance(base[k], str):
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
                base[k] = repository_dict
            elif isinstance(base[k], dict):
                base[k] = {'type': base[k].get('type', 'git'),
                           'url': base[k].get('url', '')}
        else:
            base[k] = None

        # transform 'declared_licenses' to a list
        if 'declared_licenses' in base:
            k = 'declared_licenses'
            value = base[k]
            # e.g. "(ISC OR GPL-3.0)"
            if isinstance(value, str):
                if ' OR ' in value:
                    base[k] = value.strip('()').split(' OR ')
                else:
                    base[k] = [value]
            # e.g. {"license": {"type": "ISC", "url": "http://opensource.org/licenses/ISC"}}
            elif (isinstance(value, dict) and
                  "type" in value and isinstance(value["type"], str)):
                base[k] = [value["type"]]
            # e.g. {"licenses": [{"type": "MIT", "url": "http://..."},
            #                    {"type": "Apache-2.0", "url": "http://..."}]}
            elif isinstance(value, list):
                licenses = []
                for l in value:
                    if isinstance(l, dict) and \
                       "type" in l and isinstance(l["type"], str):
                        licenses.append(l["type"])
                base[k] = licenses

        # transform dict dependencies into flat list of strings
        # name and version spec are separated by ' ' space
        for dep_section in ('dependencies', 'devel_dependencies'):
            # we also want to translate empty dict to empty list
            if isinstance(base.get(dep_section), dict):
                flat_deps = []
                for name, spec in base[dep_section].items():
                    flat_deps.append('{} {}'.format(name, spec))
                base[dep_section] = flat_deps

        engines = base['engines']
        # example: request@2.16.6: {"engines":["node >= 0.8.0"]}
        if isinstance(engines, list):
            base['engines'] = {}
            for engine in engines:
                if isinstance(engine, str):
                    # ["node >= 0.8.0"]  ->  {"node": ">=0.8.0"}
                    splits = engine.split()
                    if len(splits) == 3:
                        name, operator, version = splits
                        base['engines'][name] = operator + version
                    elif len(splits) == 2:
                        name, operator_version = splits
                        base['engines'][name] = operator_version
        elif isinstance(engines, str):
            # 'node 4.2.3' -> {"node": "4.2.3"}
            name, version = engines.split()
            base['engines'] = {name: version}
        if base['engines'] is not None:
            for name, version_spec in base['engines'].items():
                if ' ' in version_spec:
                    # ">= 0.8.0"  ~>  ">=0.8.0"
                    base['engines'][name] = version_spec.replace(' ', '')

        if isinstance(base['keywords'], str):
            base['keywords'] = self._split_keywords(base['keywords'], separator=',')

        if isinstance(base['files'], str):
            base['files'] = self._split_keywords(base['files'])

        def _process_level(level, collect):
            """Process a `level` of dependency tree and store data in `collect`."""
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
            lockfile['version'] = lockfile.pop('npm-shrinkwrap-version', "")
            lockfile['runtime'] = data.get('_nodeVersion', "")
            lockfile['dependencies'] = dependencies
            lockfile.pop('node-version', None)

        base['_tests_implemented'] = self._are_tests_implemented(base)
        return base

    @staticmethod
    def _identify_gh_repo(homepage):
        """Return code repository dict filled with homepage."""
        if parse_gh_repo(homepage):
            return {'url': homepage, 'type': 'git'}
        return None

    @staticmethod
    def _split_keywords(keywords, separator=None):
        """Split keywords (string) with separator.

        If separator is not specified, use either colon or whitespace.
        """
        if keywords is None:
            return []
        if isinstance(keywords, list):
            return keywords
        if separator is None:
            separator = ',' if ',' in keywords else ' '
        keywords = keywords.split(separator)
        keywords = [kw.strip() for kw in keywords]
        return keywords

    def _handle_python(self, data):
        """Handle setup.py."""
        if 'error' in data:
            # mercator by default (MERCATOR_INTERPRET_SETUP_PY=false) doesn't interpret setup.py
            return {}

        key_map = (('url', 'homepage'),
                   ('install_requires', 'dependencies'), ('name',),
                   ('description',), ('version',))

        transformed = self.transform_keys(data, key_map)
        transformed['declared_licenses'] = self._split_keywords(data.get('license'), separator=',')
        transformed['author'] = self._join_name_email(data, 'author', 'author_email')
        transformed['code_repository'] = (self._identify_gh_repo(data.get('url')) or
                                          self._identify_gh_repo(data.get('download_url')))
        transformed['keywords'] = self._split_keywords(data.get('keywords'))
        return transformed

    def _handle_python_dist(self, data):
        """Handle PKG-INFO."""
        details = data.get('extensions', {}).get('python.details', None)
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
            result = {'author': author, 'homepage': homepage,
                      'description': data.get('summary', None),
                      'dependencies': sorted(dependencies), 'name': data.get('name', None),
                      'version': data.get('version', None),
                      'declared_licenses': self._split_keywords(data.get('license'), separator=',')}
        else:
            key_map = (('summary', 'description'), ('requires_dist', 'dependencies'), ('name',),
                       ('home-page', 'homepage'), ('version',), ('platform',), )

            result = self.transform_keys(data, key_map)
            result['author'] = self._join_name_email(data, 'author', 'author-email')
            result['declared_licenses'] = self._split_keywords(data.get('license'), separator=',')

        result['code_repository'] = (self._identify_gh_repo(data.get('home-page')) or
                                     self._identify_gh_repo(data.get('download-url')))
        result['keywords'] = self._split_keywords(data.get('keywords'))

        return result

    def _handle_python_requirementstxt(self, data):
        """Handle requirements.txt."""
        result = {'dependencies': data.get('dependencies', [])}
        return result

    def _handle_java(self, data):
        """Handle data from pom.xml."""
        # we expect pom.xml to be there, since it's always downloaded to top level by InitTask
        pom = data.get('pom.xml')
        if pom is None:
            return None

        key_map = (('name',), ('version', ), ('description', ), ('url', 'homepage'),
                   ('licenses', 'declared_licenses'))
        # handle licenses
        transformed = self.transform_keys(pom, key_map)
        if transformed['name'] is None:
            transformed['name'] = "{}:{}".format(pom.get('groupId'), pom.get('artifactId'))
        # dependencies with scope 'compile' and 'runtime' are needed at runtime;
        # dependencies with scope 'provided' are not necessarily runtime dependencies,
        # but they are commonly used for example in web applications
        dependencies_dict = pom.get('dependencies', {}).get('compile', {})
        dependencies_dict.update(pom.get('dependencies', {}).get('runtime', {}))
        dependencies_dict.update(pom.get('dependencies', {}).get('provided', {}))
        # dependencies with scope 'test' are only needed for testing;
        dev_dependencies_dict = pom.get('dependencies', {}).get('test', {})

        transformed['dependencies'] = [k.rstrip(':') + ' ' + v
                                       for k, v in dependencies_dict.items()]

        transformed['devel_dependencies'] = [k.rstrip(':') + ' ' + v
                                             for k, v in dev_dependencies_dict.items()]

        # handle code_repository
        if 'scm_url' in pom:
            # TODO: there's no way we can tell 100 % what the type is, but we could
            #  try to handle at least some cases, e.g. github will always be git etc
            repo_type = 'git' if parse_gh_repo(pom['scm_url']) else 'unknown'
            transformed['code_repository'] = {'url': pom['scm_url'],
                                              'type': repo_type}

        return transformed

    @staticmethod
    def _extract_engine_requirements(data, key):
        """Extract requirements.

        This is what mercator creates when parsing rubygems metadata.yaml
        key is for example 'required_rubygem_version'
        key: {
             "requirements": [
               [">=", {"version": "1.9.2"}]
             ]
           }
        extract just the ">=1.9.2" from it.
        """
        try:
            requirement = data[key]['requirements'][0]
            return requirement[0] + requirement[1]['version']
        except Exception:
            return None

    def _handle_rubygems(self, data):
        """Handle metadata from rubygems` metadata.yaml."""
        key_map = (('author',), ('authors',), ('email',), ('name',), ('version',), ('homepage',),
                   (('license', 'licenses',), 'declared_licenses'),
                   ('dependencies',), ('devel_dependencies',), ('description',),
                   ('metadata',), ('platform',), )
        transformed = self.transform_keys(data, key_map)

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
        if isinstance(transformed.get('version'), dict):
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

    def _handle_gofedlib(self, data):
        """Handle metadata from gofedlib."""
        key_map = (('version',), ('name',), ('code_repository',))
        transformed = self.transform_keys(data, key_map)

        raw_dependencies = set(data.get('deps-main', []) + data.get('deps-packages', []))
        dependencies = []
        for dependency in raw_dependencies:
            scheme = '{}://'.format(urlparse(dependency).scheme)
            if dependency.startswith(scheme):
                dependency = dependency.replace(scheme, '', 1)
            dependencies.append(dependency)

        transformed['dependencies'] = dependencies
        return transformed

    def _handle_go_glide(self, data):
        """Handle metadata from golang's glide.

        https://glide.readthedocs.io/en/latest/glide.yaml
        """
        def _import2dependencies(import_list):
            # transform
            # [{"package": "github.com/Masterminds/glide",
            #   "subpackages": ["cfg, util"],
            #   "version": "~0.13.1"}]
            # to
            # ["github.com/Masterminds/glide/cfg ~0.13.1",
            #  "github.com/Masterminds/glide/util ~0.13.1"]
            dependencies = []
            for dep in import_list:
                if dep.get('subpackages'):
                    for sp in dep['subpackages']:
                        _dep = "{name}/{subpackage} {version}".\
                            format(name=dep['package'],
                                   subpackage=sp,
                                   version=dep.get('version', '')).strip()
                        dependencies.append(_dep)
                else:
                    _dep = "{name} {version}".format(name=dep['package'],
                                                     version=dep.get('version', '')).strip()
                    dependencies.append(_dep)
            return dependencies

        key_map = (('package', 'name'),
                   ('homepage',),
                   ('_dependency_tree_lock_file', '_dependency_tree_lock'),)
        transformed = self.transform_keys(data, key_map)

        # transform
        # [{"email": "technosophos@gmail.com", "name": "Matt Butcher"},
        #  {"email": "matt@mattfarina.com", "name": "Matt Farina"}]
        # to
        # "Matt Butcher <technosophos@gmail.com>, Matt Farina <matt@mattfarina.com>"
        if data.get('owners'):
            transformed['author'] = ', '.join((self._join_name_email(o)
                                               for o in data['owners']))

        if data.get('license'):
            transformed['declared_licenses'] = [data['license']]

        transformed['dependencies'] = _import2dependencies(data.get('import', []))
        transformed['devel_dependencies'] = _import2dependencies(data.get('testImport', []))
        # rename 'import' key to 'dependencies'
        if 'import' in transformed.get('_dependency_tree_lock', {}):
            transformed['_dependency_tree_lock']['dependencies'] =\
                transformed['_dependency_tree_lock'].pop('import')

        return transformed

    def _handle_dotnet_solution(self, data):
        """Handle nuget package metadata."""
        if not data.get('Metadata'):
            return {}
        data = data['Metadata']
        key_map = (('Id', 'name'), ('Description',),
                   ('ProjectUrl', 'homepage'),
                   # ('Summary',), ('Copyright',),
                   # ('RequireLicenseAcceptance', 'require_license_acceptance'),
                   )
        transformed = self.transform_keys(data, key_map)

        if data.get('Authors'):
            transformed['author'] = ','.join(data['Authors'])

        if data.get('LicenseUrl'):
            from f8a_worker.process import IndianaJones  # download_file
            # It's here due to circular dependencies
            from f8a_worker.workers import LicenseCheckTask  # run_scancode
            transformed['declared_licenses'] = [data['LicenseUrl']]
            with TemporaryDirectory() as tmpdir:
                try:
                    # Get file from 'LicenseUrl' and let LicenseCheckTask decide what license it is
                    if IndianaJones.download_file(data['LicenseUrl'], tmpdir):
                        scancode_results = LicenseCheckTask.run_scancode(tmpdir)
                        if scancode_results.get('summary', {}).get('sure_licenses'):
                            transformed['declared_licenses'] =\
                                scancode_results['summary']['sure_licenses']
                except Exception:
                    # Don't raise if IndianaJones or LicenseCheckTask fail
                    pass

        # transform
        # "DependencyGroups": [
        #    {
        #        "Packages": [
        #            {
        #                "Id": "NETStandard.Library",
        #                "VersionRange": {"OriginalString": "1.6.0"}
        #            }
        #        ]
        #    }
        # ]
        # to ["NETStandard.Library 1.6.0"]
        deps = set()
        for dep_group in data.get('DependencyGroups', []):
            for package in dep_group.get('Packages', []):
                deps.add('{} {}'.format(package.get('Id', ''),
                                        package.get('VersionRange', {}).get('OriginalString', '')))
        if deps:
            transformed['dependencies'] = list(deps)

        repository = data.get('Repository')
        if isinstance(repository, dict) and repository:
            transformed['code_repository'] = {'type': repository.get('Type'),
                                              'url': repository.get('Url')}
        elif 'ProjectUrl' in data:
            transformed['code_repository'] = self._identify_gh_repo(data['ProjectUrl'])

        version = data.get('Version')
        if isinstance(version, dict) and version:
            transformed['version'] = '{}.{}.{}'.format(version.get('Major', ''),
                                                       version.get('Minor', ''),
                                                       version.get('Patch', ''))

        if data.get('Tags'):
            transformed['keywords'] = self._split_keywords(data['Tags'])

        return transformed

    def handle_data(self, data, keep_path=False):
        """Run corresponding handler based on ecosystem."""
        def _passthrough(unused):
            # log.debug('ecosystem %s not handled', data['ecosystem'])
            pass

        "Arbitrate between various build/packaging systems"
        # TODO: some fallback if ecosystem is not matched
        switch = {'python': self._handle_python,
                  'python-dist': self._handle_python_dist,
                  'python-requirementstxt': self._handle_python_requirementstxt,
                  'npm': self._handle_javascript,
                  'java-pom': self._handle_java,
                  'ruby': self._handle_rubygems,
                  'dotnetsolution': self._handle_dotnet_solution,
                  'gofedlib': self._handle_gofedlib,
                  'go-glide': self._handle_go_glide}

        result = switch.get(data['ecosystem'].lower(), _passthrough)(data.get('result', {}))
        if result is None:
            result = {}

        if keep_path:
            result['path'] = data.get('path', None)
        result['ecosystem'] = data['ecosystem'].lower()
        return result

    @staticmethod
    def get_outermost_items(list_):
        """Sort by the depth of the path so the outermost come first."""
        sorted_list = sorted(list_, key=lambda a: len(a['path'].split(path.sep)))
        if sorted_list:
            outermost_len = len(sorted_list[0]['path'].split(path.sep))
            sorted_list = [i for i in sorted_list if
                           len(i['path'].split(path.sep)) == outermost_len]
        return sorted_list

    @staticmethod
    def _sanitize_data(data):
        """Make sure deps are never 'null'."""
        if 'dependencies' in data and data['dependencies'] is None:
            data['dependencies'] = []
        if 'devel_dependencies' in data and data['devel_dependencies'] is None:
            data['devel_dependencies'] = []

        return data

    @staticmethod
    def _dict2json(o, pretty=True):
        """Serialize dictionary to json."""
        kwargs = {}
        if pretty:
            kwargs['sort_keys'] = True,
            kwargs['separators'] = (',', ': ')
            kwargs['indent'] = 2

        return json.dumps(o, **kwargs)

    def main(self):
        """Read Mercator produced data from stdin and process."""
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
