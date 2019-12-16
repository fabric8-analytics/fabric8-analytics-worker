"""Data normalizers for Python."""

from f8a_worker.data_normalizer import AbstractDataNormalizer


class PythonDataNormalizer(AbstractDataNormalizer):
    """Python data normalizer.

    This normalizer handles data extracted from setup.py files by mercator-go.
    """

    _key_map = (
        ('url', 'homepage'),
        ('install_requires', 'dependencies'), ('name',),
        ('description',), ('version',)
    )

    def __init__(self, mercator_json):
        """Initialize function."""
        if 'error' in mercator_json:
            # mercator by default (MERCATOR_INTERPRET_SETUP_PY=false) doesn't interpret setup.py
            mercator_json = {}
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for setup.py (Python)."""
        if not self._raw_data:
            return {}

        self._data['declared_licenses'] = self._split_keywords(
            self._raw_data.get('license'), separator=','
        )
        self._data['author'] = self._join_name_email(self._raw_data, 'author', 'author_email')
        self._data['code_repository'] = (
                self._identify_gh_repo(self._raw_data.get('url')) or
                self._identify_gh_repo(self._raw_data.get('download_url'))
        )
        self._data['keywords'] = self._split_keywords(self._raw_data.get('keywords'))
        return self._data


class PythonDistDataNormalizer(AbstractDataNormalizer):
    """Python-dist data normalizer.

    This normalizer handles data extracted from PKG-INFO files by mercator-go.
    """

    _key_map = (
        ('summary', 'description'),
        ('requires_dist', 'dependencies'),
        ('name',),
        ('home-page', 'homepage'),
        ('version',),
        ('platform',),
    )

    def __init__(self, mercator_json):
        """Initialize function."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for PKG-INFO (Python)."""
        details = self._raw_data.get('extensions', {}).get('python.details', None)
        if details is not None:
            contacts = details.get('contacts', [])
            urls = details.get('project_urls', {})
            # pep-0426/#mapping-dependencies-to-development-and-distribution-activities
            #  says that in runtime, this package will need both run_requires and meta_requires
            requires = \
                self._raw_data.get('run_requires', []) + self._raw_data.get('meta_requires', [])
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
            self._data = {
                'author': author, 'homepage': homepage,
                'description': self._raw_data.get('summary', None),
                'dependencies': sorted(dependencies), 'name': self._raw_data.get('name', None),
                'version': self._raw_data.get('version', None),
                'declared_licenses': self._split_keywords(
                    self._raw_data.get('license'), separator=','
                )
            }
        else:
            self._data['author'] = self._join_name_email(self._raw_data, 'author', 'author-email')
            self._data['declared_licenses'] = self._split_keywords(
                self._raw_data.get('license'), separator=','
            )

        self._data['code_repository'] = (
                self._identify_gh_repo(self._raw_data.get('home-page')) or
                self._identify_gh_repo(self._raw_data.get('download-url'))
        )
        self._data['keywords'] = self._split_keywords(self._raw_data.get('keywords'))

        return self._data


class PythonRequirementsTxtDataNormalizer(AbstractDataNormalizer):
    """Python-dist data normalizer.

    This normalizer handles data extracted from requirements.txt files by mercator-go.
    """

    def __init__(self, mercator_json):
        """Initialize function."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for requirements.txt (Python)."""
        result = {'dependencies': self._raw_data.get('dependencies', [])}
        return result
