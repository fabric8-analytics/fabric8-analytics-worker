"""Data normalizers for JavaScript."""


from f8a_worker.data_normalizer import AbstractDataNormalizer


class NpmDataNormalizer(AbstractDataNormalizer):
    """NPM data normalizer.

    This normalizer handles data extracted from package.json files by mercator-go.
    """

    _key_map = (
        (('license', 'licenses',), 'declared_licenses'),
        ('_dependency_tree_lock_file', '_dependency_tree_lock'),
        ('homepage',),
        ('version',),
        ('description',),
        ('dependencies',),
        ('devDependencies', 'devel_dependencies'),
        ('bugs', 'bug_reporting'),
        ('author',),
        ('contributors',),
        ('maintainers',),
        ('repository', 'code_repository'),
        ('name',),
        (('engine', 'engines'), 'engines'),
        ('gitHead', 'git_head'),
        ('readme',),
        ('scripts',),
        ('files',),
        ('keywords',),
    )

    def __init__(self, mercator_json):
        """Constructor."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for NPM."""
        self._transform_bug_reporting()
        self._transform_author()
        self._transform_contributors()
        self._transform_maintainers()
        self._transform_code_repository()
        self._transform_declared_licenses()
        self._transform_description()
        self._transform_dependencies()
        self._transform_engines()
        self._transform_keywords()
        self._transform_files()
        self._transform_homepage()
        self._transform_dependency_lock_file()
        self._transform_tests_implemented()

        return self._data

    def _are_tests_implemented(self):
        """Say whether a package implements tests.

        Metadata info only isn't much reliable, but we have some indicators.
        """
        # NPM - package.json: metadata can contain 'scripts'.'test'
        if 'scripts' in self._data:  # added by _handle_javascript()
            if self._data['scripts'] is None:
                return False
            elif type(self._data['scripts']) is dict:
                test_script = self._data['scripts'].get('test', '')
                # Existing test_script doesn't say much about whether it really runs some tests.
                # For example: 'npm init' uses 'echo "Error: no test specified" && exit 1'
                # as a default value of 'scripts'.'test'
                return isinstance(test_script, str) and test_script != '' \
                    and 'Error: no test specified' not in test_script
            else:
                return False

    def _transform_bug_reporting(self):
        if isinstance(self._data.get('bug_reporting'), dict):
            self._data['bug_reporting'] = self._join_name_email(self._data['bug_reporting'], 'url')
        else:
            self._data['bug_reporting'] = None

    def _transform_author(self):
        if isinstance(self._data.get('author'), dict):
            self._data['author'] = self._join_name_email(self._data['author'])
        elif isinstance(self._data.get('author'), list):
            # Process it even it violates https://docs.npmjs.com/files/package.json
            if isinstance(self._data['author'][0], dict):
                self._data['author'] = self._join_name_email(self._data['author'][0])
            elif isinstance(self._data['author'][0], str):
                self._data['author'] = self._data['author'][0]
        else:
            self._data['author'] = None

    def _transform_contributors(self):
        if self._data['contributors'] is not None:
            if isinstance(self._data['contributors'], list):
                self._data['contributors'] = self._rf(
                    self._join_name_email(m) for m in self._data['contributors']
                )
            elif isinstance(self._data['contributors'], dict):
                self._data['contributors'] = self._rf(
                    [self._join_name_email(self._data['contributors'])]
                )
            elif isinstance(self._data['contributors'], str):
                self._data['contributors'] = self._rf([self._data['contributors']])

    def _transform_maintainers(self):
        if isinstance(self._data['maintainers'], list):
            self._data['maintainers'] = self._rf(
                self._join_name_email(m) for m in self._data['maintainers']
            )
        elif isinstance(self._data['maintainers'], str):
            self._data['maintainers'] = self._rf([self._data['maintainers']])

    def _transform_code_repository(self):
        key = 'code_repository'
        if self._data[key]:
            # 'a/b' -> {'type': 'git', 'url': 'https://github.com/a/b.git'}
            if isinstance(self._data[key], str):
                url = self._data[key]
                if url.count('/') == 1:  # e.g. 'expressjs/express'
                    if ':' in url:
                        if url.startswith('bitbucket:'):
                            owner, repo = url[len('bitbucket:'):].split('/')
                            url = 'https://{owner}@bitbucket.org/{owner}/{repo}.git'.format(
                                owner=owner, repo=repo
                            )
                        if url.startswith('gitlab:'):
                            url = 'https://gitlab.com/' + url[len('gitlab:'):] + '.git'
                    else:  # default is github
                        url = 'https://github.com/' + url + '.git'
                repository_dict = {'type': 'git', 'url': url}
                self._data[key] = repository_dict
            elif isinstance(self._data[key], dict):
                self._data[key] = {
                    'type': self._data[key].get('type', 'git'),
                    'url': self._data[key].get('url', '')
                }
        else:
            self._data[key] = None

    def _transform_declared_licenses(self):
        # transform 'declared_licenses' to a list
        k = 'declared_licenses'
        value = self._data[k]

        if not value:
            self._data[k] = None
            return

        if isinstance(value, str):
            # e.g. "(ISC OR GPL-3.0)"
            self._transform_declared_licenses_str(k, value)
        elif isinstance(value, dict):
            # e.g. {"license": {"type": "ISC", "url": "http://opensource.org/licenses/ISC"}}
            self._transform_declared_licenses_dict(k, value)
        elif isinstance(value, list):
            # e.g. {"licenses": [{"type": "MIT", "url": "http://..."},
            #                    {"type": "Apache-2.0", "url": "http://..."}]}
            self._transform_declared_licenses_list(k, value)

    def _transform_declared_licenses_str(self, k, value):
        if ' OR ' in value:
            self._data[k] = value.strip('()').split(' OR ')
        else:
            self._data[k] = [value]

    def _transform_declared_licenses_dict(self, k, value):
        if isinstance(value.get("type"), str):
            self._data[k] = [value["type"]]
        elif isinstance(value.get("name"), str):
            self._data[k] = [value["name"]]

    def _transform_declared_licenses_list(self, k, value):
        licenses = []
        for l in value:
            if isinstance(l, dict):
                if isinstance(l.get("type"), str):
                    licenses.append(l["type"])
                elif isinstance(l.get("name"), str):
                    licenses.append(l["name"])
        self._data[k] = licenses

    def _transform_description(self):
        key = 'description'
        value = self._data[key]
        if isinstance(value, str):
            return
        elif isinstance(value, (list, tuple)):
            self._data[key] = ' '.join(value)
        elif value is not None:
            self._data[key] = str(value)
        else:
            self._data[key] = None

    def _transform_dependencies(self):
        # transform dict dependencies into flat list of strings
        # name and version spec are separated by ' ' space
        for dep_section in ('dependencies', 'devel_dependencies'):
            if isinstance(self._data.get(dep_section), list):
                return
            # we also want to translate empty dict to empty list
            elif isinstance(self._data.get(dep_section), dict):
                flat_deps = []
                for name, spec in self._data[dep_section].items():
                    flat_deps.append('{} {}'.format(name, spec))
                self._data[dep_section] = flat_deps
            else:
                # some trash, like for example a boolean value; ignore...
                self._data[dep_section] = []

    def _transform_engines(self):
        engines = self._data['engines']
        if isinstance(engines, list):
            # example: request@2.16.6: {"engines":["node >= 0.8.0"]}
            self._transform_engines_list(engines)
        elif isinstance(engines, str):
            # 'node 4.2.3' -> {"node": "4.2.3"}
            self._transform_engines_str(engines)

        if self._data['engines'] is not None:
            for name, version_spec in self._data['engines'].items():
                if ' ' in version_spec:
                    # ">= 0.8.0"  ~>  ">=0.8.0"
                    self._data['engines'][name] = version_spec.replace(' ', '')

    def _transform_engines_list(self, engines):
        self._data['engines'] = {}
        for engine in engines:
            if isinstance(engine, str):
                # ["node >= 0.8.0"]  ->  {"node": ">=0.8.0"}
                splits = engine.split()
                if len(splits) == 3:
                    name, operator, version = splits
                    self._data['engines'][name] = operator + version
                elif len(splits) == 2:
                    name, operator_version = splits
                    self._data['engines'][name] = operator_version

    def _transform_engines_str(self, engines):
        try:
            name, version = engines.split()
            self._data['engines'] = {name: version}
        except ValueError:
            # For malformed data: '8.3' -> {}
            self._data['engines'] = {}

    def _transform_keywords(self):
        if isinstance(self._data['keywords'], str):
            self._data['keywords'] = self._split_keywords(self._data['keywords'])

    def _transform_files(self):
        if isinstance(self._data['files'], str):
            self._data['files'] = self._split_keywords(self._data['files'])

    def _transform_homepage(self):
        if isinstance(self._data['homepage'], dict):
            self._data['homepage'] = self._data['homepage'].get('url', '')

    def _transform_dependency_lock_file(self):
        def _process_level(level, collect):
            """Process a `level` of dependency tree and store data in `collect`."""
            for name, data in level.items():
                deps = []
                item = {
                    'name': name,
                    'version': data.get('version', ''),
                    'specification': data.get('from', None),
                    'resolved': data.get('resolved', None),
                    'dependencies': deps,
                    'dev': data.get('dev', False)
                }
                collect.append(item)
                _process_level(data.get('dependencies', {}), deps)

        lockfile = self._data.get('_dependency_tree_lock')

        if lockfile is not None:
            dependencies = []
            _process_level(lockfile.get('dependencies', {}), dependencies)
            lockfile['version'] = lockfile.pop('npm-shrinkwrap-version', '')
            lockfile['runtime'] = self._raw_data.get('_nodeVersion', '')
            lockfile['dependencies'] = dependencies

            # Drop rest of the unknown/unwanted keys
            for key in list(lockfile.keys()):
                if key not in ('dependencies', 'version', 'runtime', 'name', 'hash', 'updated'):
                    lockfile.pop(key)

    def _transform_tests_implemented(self):
        self._data['_tests_implemented'] = self._are_tests_implemented()
