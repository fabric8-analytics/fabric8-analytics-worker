"""Data normalizers for Go."""

from f8a_worker.data_normalizer import AbstractDataNormalizer
from urllib.parse import urlparse


class GoGlideDataNormalizer(AbstractDataNormalizer):
    """Glide data normalizer.

    This normalizer handles data extracted from glide.yaml files by mercator-go.
    """

    _key_map = (
        ('package', 'name'),
        ('homepage',),
        ('_dependency_tree_lock_file', '_dependency_tree_lock'),
    )

    def __init__(self, mercator_json):
        """Constructor."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for glide.yaml (Go)."""
        # transform
        # [{"email": "technosophos@gmail.com", "name": "Matt Butcher"},
        #  {"email": "matt@mattfarina.com", "name": "Matt Farina"}]
        # to
        # "Matt Butcher <technosophos@gmail.com>, Matt Farina <matt@mattfarina.com>"
        if self._raw_data.get('owners'):
            self._data['author'] = ', '.join(
                (self._join_name_email(o) for o in self._raw_data['owners'])
            )

        if self._raw_data.get('license'):
            self._data['declared_licenses'] = [self._raw_data['license']]

        self._data['dependencies'] = self._import2dependencies(self._raw_data.get('import', []))
        self._data['devel_dependencies'] = self._import2dependencies(
            self._raw_data.get('testImport', [])
        )
        # rename 'import' key to 'dependencies'
        if 'import' in self._data.get('_dependency_tree_lock', {}):
            self._data['_dependency_tree_lock']['dependencies'] = \
                self._data['_dependency_tree_lock'].pop('import')

        return self._data

    def _import2dependencies(self, import_list):
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
                    _dep = "{name}/{subpackage} {version}".format(
                        name=dep['package'],
                        subpackage=sp,
                        version=dep.get('version', '')
                    ).strip()
                    dependencies.append(_dep)
            else:
                _dep = "{name} {version}".format(
                    name=dep['package'],
                    version=dep.get('version', '')
                ).strip()
                dependencies.append(_dep)
        return dependencies


class GodepsDataNormalizer(AbstractDataNormalizer):
    """Godeps data normalizer.

    This normalizer handles data extracted from Godeps.json files by mercator-go.
    """

    def __init__(self, mercator_json):
        """Constructor."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for Godeps.json (Go)."""
        dependencies = []

        for entry in self._raw_data.get('Deps', []):
            package = entry.get('ImportPath')
            version = entry.get('Rev', '')

            if not package:
                # we need at least package name...
                continue

            dependency = '{p} {v}'.format(p=package, v=version)
            dependencies.append(dependency)

        self._data['dependencies'] = dependencies

        return self._data


class GoFedlibDataNormalizer(AbstractDataNormalizer):
    """GoFedlib data normalizer.

    This normalizer handles output from gofedlib command used by mercator worker.
    """

    _key_map = (
        ('version',),
        ('name',),
        ('code_repository',)
    )

    def __init__(self, mercator_json):
        """Constructor."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from gofedlib (Go)."""
        raw_dependencies = set(
            self._raw_data.get('deps-main', []) + self._raw_data.get('deps-packages', [])
        )
        dependencies = []
        for dependency in raw_dependencies:
            scheme = '{}://'.format(urlparse(dependency).scheme)
            if dependency.startswith(scheme):
                dependency = dependency.replace(scheme, '', 1)
            dependencies.append(dependency)

        self._data['dependencies'] = dependencies
        return self._data
