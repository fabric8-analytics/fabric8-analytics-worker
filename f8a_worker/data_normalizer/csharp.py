"""Data normalizers for C#."""

from tempfile import TemporaryDirectory
from f8a_worker.data_normalizer import AbstractDataNormalizer


class NugetDataNormalizer(AbstractDataNormalizer):
    """Nuget data normalizer.

    This normalizer handles data extracted from .nuspec files by mercator-go.
    """

    _key_map = (
        ('Id', 'name'),
        ('Description',),
        ('ProjectUrl', 'homepage'),
        # ('Summary',), ('Copyright',),
        # ('RequireLicenseAcceptance', 'require_license_acceptance'),
    )

    def __init__(self, mercator_json):
        """Initialize function."""
        metadata = mercator_json.get('Metadata', {})
        super().__init__(metadata)

    def normalize(self):
        """Normalize output from Mercator for .nuspec (Nuget)."""
        if not self._raw_data:
            return {}

        if self._raw_data.get('Authors'):
            self._data['author'] = ','.join(self._raw_data['Authors'])

        self._transform_licenses()

        self._transform_dependencies()

        repository = self._raw_data.get('Repository')
        if isinstance(repository, dict) and repository:
            self._data['code_repository'] = {
                'type': repository.get('Type'),
                'url': repository.get('Url')
            }
        elif 'ProjectUrl' in self._raw_data:
            self._data['code_repository'] = self._identify_gh_repo(self._raw_data['ProjectUrl'])

        version = self._raw_data.get('Version')
        if isinstance(version, dict) and version:
            self._data['version'] = '{}.{}.{}'.format(
                version.get('Major', ''),
                version.get('Minor', ''),
                version.get('Patch', '')
            )

        if self._raw_data.get('Tags'):
            self._data['keywords'] = self._split_keywords(self._raw_data['Tags'])

        return self._data

    def _transform_licenses(self):
        if self._raw_data.get('LicenseUrl'):
            from f8a_worker.process import IndianaJones  # download_file
            # It's here due to circular dependencies
            from f8a_worker.workers import LicenseCheckTask  # run_scancode
            self._data['declared_licenses'] = [self._raw_data['LicenseUrl']]
            with TemporaryDirectory() as tmpdir:
                try:
                    # Get file from 'LicenseUrl' and let LicenseCheckTask decide what license it is
                    if IndianaJones.download_file(self._raw_data['LicenseUrl'], tmpdir):
                        scancode_results = LicenseCheckTask.run_scancode(tmpdir)
                        if scancode_results.get('summary', {}).get('sure_licenses'):
                            self._data['declared_licenses'] = \
                                scancode_results['summary']['sure_licenses']
                except Exception:
                    # Don't raise if IndianaJones or LicenseCheckTask fail
                    pass

    def _transform_dependencies(self):
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
        for dep_group in self._raw_data.get('DependencyGroups', []):
            for package in dep_group.get('Packages', []):
                deps.add('{} {}'.format(package.get('Id', ''),
                                        package.get('VersionRange', {}).get('OriginalString', '')))
        if deps:
            self._data['dependencies'] = list(deps)
