"""Data normalizers for Java."""

from f8a_worker.data_normalizer import AbstractDataNormalizer
from f8a_worker.utils import parse_gh_repo


class MavenDataNormalizer(AbstractDataNormalizer):
    """Maven data normalizer.

    This normalizer handles data extracted from pom.xml files by mercator-go.
    """

    _key_map = (
        ('name',),
        ('version',),
        ('description',),
        ('url', 'homepage'),
        ('licenses', 'declared_licenses')
    )

    def __init__(self, mercator_json):
        """Initialize function."""
        pom = mercator_json.get('pom.xml', {})
        super().__init__(pom)

    def normalize(self):
        """Normalize output from Mercator for pom.xml (Maven)."""
        if not self._raw_data:
            return {}

        if self._data['name'] is None:
            self._data['name'] = "{}:{}".format(
                self._raw_data.get('groupId'), self._raw_data.get('artifactId')
            )
        # dependencies with scope 'compile' and 'runtime' are needed at runtime;
        # dependencies with scope 'provided' are not necessarily runtime dependencies,
        # but they are commonly used for example in web applications
        dependencies_dict = self._raw_data.get('dependencies', {}).get('compile', {})
        dependencies_dict.update(self._raw_data.get('dependencies', {}).get('runtime', {}))
        dependencies_dict.update(self._raw_data.get('dependencies', {}).get('provided', {}))
        # dependencies with scope 'test' are only needed for testing;
        dev_dependencies_dict = self._raw_data.get('dependencies', {}).get('test', {})

        self._data['dependencies'] = [
            k.rstrip(':') + ' ' + v for k, v in dependencies_dict.items()
        ]

        self._data['devel_dependencies'] = [
            k.rstrip(':') + ' ' + v for k, v in dev_dependencies_dict.items()
        ]

        # handle code_repository
        if 'scm_url' in self._raw_data:
            # TODO: there's no way we can tell 100 % what the type is, but we could
            #  try to handle at least some cases, e.g. github will always be git etc
            repo_type = 'git' if parse_gh_repo(self._raw_data['scm_url']) else 'unknown'
            self._data['code_repository'] = {
                'url': self._raw_data['scm_url'], 'type': repo_type
            }

        return self._data


class GradleDataNormalizer(AbstractDataNormalizer):
    """Gradle data normalizer.

    This normalizer handles data extracted from gradle.build files by mercator-go.
    """

    def __init__(self, mercator_json):
        """Initialize function."""
        super().__init__(mercator_json)

    def normalize(self):
        """Normalize output from Mercator for gradle.build (Gradle)."""
        build_dependencies = list()
        for d in self._raw_data.get('buildscript', {}).get('dependencies', {}):
            build_dependencies.append(self._parse_gradle_dependencies(d))
        self._data['devel_dependencies'] = build_dependencies
        dependencies = []
        for d in self._raw_data.get('subprojects', {}).get('dependencies', {}):
            dependencies.append(self._parse_gradle_dependencies(d))
        for d in self._raw_data.get('dependencies', {}):
            dependencies.append(self._parse_gradle_dependencies(d))
        self._data['dependencies'] = dependencies
        return self._data

    def _parse_gradle_dependencies(self, dependency_entry):
        """Parse Gradle dependency entry."""
        # I am not using our GAV converter since output coming mercator is rather broken
        a = dict(groupId='', artifactId='', version='')

        a['artifactId'] = dependency_entry.get('name')
        a['groupId'] = dependency_entry.get('group')
        a['version'] = dependency_entry.get('version')

        if dependency_entry.get('name').count(':') == 2:
            a['groupId'], a['artifactId'], a['version'] = dependency_entry.get('name').split(':')
            a['groupId'] = a['groupId'].replace("\"", "")

        return a
