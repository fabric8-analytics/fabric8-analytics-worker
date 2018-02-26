"""Classes for resolving dependencies as specified in each ecosystem."""

import anymarkup
from bs4 import BeautifulSoup
from collections import defaultdict
from functools import cmp_to_key
import logging
from lxml import etree
from operator import itemgetter
from pip.req.req_file import parse_requirements
import re
from requests import get
from xmlrpc.client import ServerProxy
from semantic_version import Version as semver_version
from subprocess import check_output
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Analysis, Ecosystem, Package, Version
from f8a_worker.utils import cwd, tempdir, TimedCommand
from f8a_worker.process import Git


logger = logging.getLogger(__name__)


class SolverException(Exception):
    """Exception to be raised in Solver."""

    pass


class Tokens(object):
    """Comparison token representation."""

    operators = ['>=', '<=', '==', '>', '<', '=', '!=']
    (GTE, LTE, EQ1, GT, LT, EQ2, NEQ) = range(len(operators))


def compare_version(a, b):
    """Compare two version strings.

    :param a: str
    :param b: str
    :return: -1 / 0 / 1
    """
    def _range(q):
        """Convert a version string to array of integers.

        "1.2.3" -> [1, 2, 3]

        :param q: str
        :return: List[int]
        """
        r = []
        for n in q.replace('-', '.').split('.'):
            try:
                r.append(int(n))
            except ValueError:
                # sort rc*, alpha, beta etc. lower than their non-annotated counterparts
                r.append(-1)
        return r

    def _append_zeros(x, num_zeros):
        """Append `num_zeros` zeros to a copy of `x` and return it.

        :param x: List[int]
        :param num_zeros: int
        :return: List[int]
        """
        nx = list(x)
        for _ in range(num_zeros):
            nx.append(0)
        return nx

    def _cardinal(x, y):
        """Make both input lists be of same cardinality.

        :param x: List[int]
        :param y: List[int]
        :return: List[int]
        """
        lx, ly = len(x), len(y)
        if lx == ly:
            return x, y
        elif lx > ly:
            return x, _append_zeros(y, lx - ly)
        else:
            return _append_zeros(x, ly - lx), y

    left, right = _cardinal(_range(a), _range(b))

    return (left > right) - (left < right)


class ReleasesFetcher(object):
    """Base class for fetching releases."""

    def __init__(self, ecosystem):
        """Initialize ecosystem."""
        self._ecosystem = ecosystem

    @property
    def ecosystem(self):
        """Get ecosystem property."""
        return self._ecosystem

    def fetch_releases(self, package):
        """Abstract method for getting list of releases versions."""
        raise NotImplementedError


class PypiReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for Pypi."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super(PypiReleasesFetcher, self).__init__(ecosystem)
        self._rpc = ServerProxy(self.ecosystem.fetch_url)

    def _search_package_name(self, package):
        """Case insensitive search.

        :param package: str, Name of the package
        :return:
        """
        def find_pypi_pkg(package):
            packages = self._rpc.search({'name': package})
            if packages:
                exact_match = [p['name']
                               for p in packages
                               if p['name'].lower() == package.lower()]
                if exact_match:
                    return exact_match.pop()
        res = find_pypi_pkg(package)
        if res is None and '-' in package:
            # this is soooo annoying; you can `pip3 install argon2-cffi and it installs
            #  argon2_cffi (underscore instead of dash), but searching through XMLRPC
            #  API doesn't find it... so we try to search for underscore variant
            #  if the dash variant isn't found
            res = find_pypi_pkg(package.replace('-', '_'))
        if res:
            return res

        raise ValueError("Package {} not found".format(package))

    def fetch_releases(self, package):
        """Fetch package releases versions.

        XML-RPC API Documentation: https://wiki.python.org/moin/PyPIXmlRpc
        Signature: package_releases(package_name, show_hidden=False)
        """
        if not package:
            raise ValueError("package")

        releases = self._rpc.package_releases(package, True)
        if not releases:
            # try again with swapped case of first character
            releases = self._rpc.package_releases(package[0].swapcase() + package[1:], True)
        if not releases:
            # if nothing was found then do case-insensitive search
            return self.fetch_releases(self._search_package_name(package))

        return package.lower(), releases


class NpmReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for NPM."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super(NpmReleasesFetcher, self).__init__(ecosystem)

    def fetch_releases(self, package):
        """Fetch package releases versions.

        Example output from the NPM endpoint:
        {
            ...
            versions: {
               "0.1.0": {},
               "0.1.2": {}
               ...
            }
        }
        """
        if not package:
            raise ValueError("package")

        r = get(self.ecosystem.fetch_url + package)
        if r.status_code == 404:
            if package.lower() != package:
                return self.fetch_releases(package.lower())
            raise ValueError("Package {} not found".format(package))

        if 'versions' not in r.json().keys():
            raise ValueError("Package {} does not have associated versions".format(package))

        return package, list(r.json()['versions'].keys())


class RubyGemsReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for Rubygems."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super(RubyGemsReleasesFetcher, self).__init__(ecosystem)

    def _search_package_name(self, package):
        """Search package on rubygems.org."""
        url = '{url}/search.json?query={pkg}'.format(url=self.ecosystem.fetch_url,
                                                     pkg=package)
        r = get(url)
        if r.status_code == 200:
            exact_match = [p['name']
                           for p in r.json()
                           if p['name'].lower() == package.lower()]
            if exact_match:
                return exact_match.pop()

        raise ValueError("Package {} not found".format(package))

    def fetch_releases(self, package):
        """Fetch package releases versions.

        Example output from the RubyGems endpoint
        [
           {
             "number": "1.0.0",
             ...
           },
           {
             "number": "2.0.0",
             ...
           }
           ...
        ]
        """
        if not package:
            raise ValueError("package")

        url = '{url}/versions/{pkg}.json'.format(url=self.ecosystem.fetch_url,
                                                 pkg=package)
        r = get(url)
        if r.status_code == 404:
            return self.fetch_releases(self._search_package_name(package))

        return package, [ver['number'] for ver in r.json()]


class NugetReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for Nuget."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super(NugetReleasesFetcher, self).__init__(ecosystem)

    @staticmethod
    def scrape_versions_from_nuget_org(package, sort_by_downloads=False):
        """Scrape 'Version History' from https://www.nuget.org/packages/<package>."""
        releases = []
        nuget_packages_url = 'https://www.nuget.org/packages/'
        page = get(nuget_packages_url + package)
        page = BeautifulSoup(page.text, 'html.parser')
        version_history = page.find(class_="version-history")
        for version in version_history.find_all(href=re.compile('/packages/')):
            version_text = version.text.replace('(current version)', '').strip()
            try:
                semver_version.coerce(version_text)
                downloads = int(version.find_next('td').text.strip().replace(',', ''))
            except ValueError:
                pass
            else:
                releases.append((version_text, downloads))
        if sort_by_downloads:
            releases.sort(key=itemgetter(1))
        return package, [p[0] for p in reversed(releases)]

    def fetch_releases(self, package):
        """Fetch package releases versions."""
        if not package:
            raise ValueError("package not specified")

        # There's an API interface which lists available releases at
        # https://api.nuget.org/v3-flatcontainer/{package}/index.json
        # But it lists also unlisted/deprecated/shouldn't-be-used versions,
        # so we don't use it.

        return self.scrape_versions_from_nuget_org(package)


class MavenReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for Maven."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super().__init__(ecosystem)

    @staticmethod
    def releases_from_maven_org(group_id, artifact_id):
        """Fetch releases versions for group_id/artifact_id from maven.org."""
        maven_url = "http://repo1.maven.org/maven2/"
        dir_path = "{g}/{a}/".format(g=group_id.replace('.', '/'), a=artifact_id)
        url = urljoin(maven_url, dir_path)
        releases = []
        page = BeautifulSoup(get(url).text, 'html.parser')
        for link in page.find_all('a'):
            if link.text.endswith('/') and link.text != '../':
                releases.append(link.text.rstrip('/'))
        return releases

    def fetch_releases(self, package):
        """Fetch package releases versions."""
        if not package:
            raise ValueError("package not specified")
        try:
            group_id, artifact_id = package.split(':')
        except ValueError as exc:
            raise ValueError("Invalid Maven coordinates: {a}".format(a=package)) from exc

        return package, self.releases_from_maven_org(group_id, artifact_id)


class GolangReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for Golang."""

    def __init__(self, ecosystem):
        """Initialize instance."""
        super(GolangReleasesFetcher, self).__init__(ecosystem)

    def fetch_releases(self, package):
        """Fetch package releases versions."""
        if not package:
            raise ValueError('package not specified')

        parts = package.split("/")[:3]
        if len(parts) == 3:  # this assumes github.com/org/project like structure
            host, org, proj = parts
            repo_url = 'git://{host}/{org}/{proj}.git'.format(host=host, org=org, proj=proj)
        elif len(parts) == 2 and parts[0] == 'gopkg.in':  # specific to gopkg.in/packages
            host, proj = parts
            repo_url = 'https://{host}/{proj}.git'.format(host=host, proj=proj)
        else:
            raise ValueError("Package {} is invalid git repository".format(package))

        output = Git.ls_remote(repo_url, args=['-q'], refs=['HEAD'])
        version, ref = output[0].split()

        if not version:
            raise ValueError("Package {} does not have associated versions".format(package))

        return package, [version]


class F8aReleasesFetcher(ReleasesFetcher):
    """Releases fetcher for internal database."""

    def __init__(self, ecosystem, database):
        """Initialize instance."""
        super(F8aReleasesFetcher, self).__init__(ecosystem)
        self.database = database

    def fetch_releases(self, package):
        """Fetch analysed versions for specific ecosystem + package from f8a."""
        query = self.database.query(Version).\
            join(Analysis).join(Package).join(Ecosystem).\
            filter(Package.name == package,
                   Ecosystem.name == self.ecosystem.name,
                   Analysis.finished_at.isnot(None))
        versions = {v.identifier for v in query}
        return package, list(sorted(versions, key=cmp_to_key(compare_version)))


class Dependency(object):
    """A Dependency consists of (package) name and version spec."""

    def __init__(self, name, spec):
        """Initialize instance."""
        self._name = name
        # spec is a list where each item is either 2-tuple (operator, version) or list of these
        # example: [[('>=', '0.6.0'), ('<', '0.7.0')], ('>', '1.0.0')] means:
        # (>=0.6.0 and <0.7.0) or >1.0.0
        self._spec = spec

    @property
    def name(self):
        """Get name property."""
        return self._name

    @property
    def spec(self):
        """Get version spec property."""
        return self._spec

    def __contains__(self, item):
        """Implement 'in' operator."""
        return self.check(item)

    def __repr__(self):
        """Return string representation of this instance."""
        return "{} {}".format(self.name, self.spec)

    def __eq__(self, other):
        """Implement '==' operator."""
        return self.name == other.name and self.spec == other.spec

    def check(self, version):
        """Check if `version` fits into our dependency specification.

        :param version: str
        :return: bool
        """
        def _compare_spec(spec):
            if len(spec) == 1:
                spec = ('=', spec[0])

            token = Tokens.operators.index(spec[0])
            comparison = compare_version(version, spec[1])
            if token in [Tokens.EQ1, Tokens.EQ2]:
                return comparison == 0
            elif token == Tokens.GT:
                return comparison == 1
            elif token == Tokens.LT:
                return comparison == -1
            elif token == Tokens.GTE:
                return comparison >= 0
            elif token == Tokens.LTE:
                return comparison <= 0
            elif token == Tokens.NEQ:
                return comparison != 0
            else:
                raise ValueError('Invalid comparison token')

        def _all(spec_):
            return all(_all(s) if isinstance(s, list) else _compare_spec(s) for s in spec_)

        return any(_all(s) if isinstance(s, list) else _compare_spec(s) for s in self.spec)


class DependencyParser(object):
    """Base class for Dependency parsing."""

    def parse(self, specs):
        """Abstract method for Dependency parsing."""
        pass

    @staticmethod
    def compose_sep(deps, separator):
        """Opposite of parse().

        :param deps: list of Dependency()
        :param separator: when joining dependencies, use this separator
        :return: dict of {name: version spec}
        """
        result = {}
        for dep in deps:
            if dep.name not in result:
                result[dep.name] = separator.join([op + ver for op, ver in dep.spec])
            else:
                result[dep.name] += separator + separator.join([op + ver for op, ver in dep.spec])
        return result


class PypiDependencyParser(DependencyParser):
    """Pypi Dependency parsing."""

    @staticmethod
    def _parse_python(spec):
        """Parse PyPI specification of a single dependency.

        :param spec: str, for example "Django>=1.5,<1.8"
        :return: [Django [[('>=', '1.5'), ('<', '1.8')]]]
        """
        def _extract_op_version(spec):
            # https://www.python.org/dev/peps/pep-0440/#compatible-release
            if spec.operator == '~=':
                version = spec.version.split('.')
                if len(version) in {2, 3, 4}:
                    if len(version) in {3, 4}:
                        del version[-1]  # will increase the last but one in next line
                    version[-1] = str(int(version[-1]) + 1)
                else:
                    raise ValueError('%r must not be used with %r' % (spec.operator, spec.version))
                return [('>=', spec.version), ('<', '.'.join(version))]
            # Trailing .* is permitted per
            # https://www.python.org/dev/peps/pep-0440/#version-matching
            elif spec.operator == '==' and spec.version.endswith('.*'):
                try:
                    result = check_output(['/usr/bin/semver-ranger', spec.version],
                                          universal_newlines=True).strip()
                    gte, lt = result.split()
                    return [('>=', gte.lstrip('>=')), ('<', lt.lstrip('<'))]
                except ValueError:
                    logger.info("couldn't resolve ==%s", spec.version)
                    return spec.operator, spec.version
            # https://www.python.org/dev/peps/pep-0440/#arbitrary-equality
            # Use of this operator is heavily discouraged, so just convert it to 'Version matching'
            elif spec.operator == '===':
                return '==', spec.version
            else:
                return spec.operator, spec.version

        def _get_pip_spec(requirements):
            """There's no `specs` field In Pip 8+, take info from `specifier` field."""
            if hasattr(requirements, 'specs'):
                return requirements.specs
            elif hasattr(requirements, 'specifier'):
                specs = [_extract_op_version(spec) for spec in requirements.specifier]
                if len(specs) == 0:
                    specs = [('>=', '0.0.0')]
                elif len(specs) > 1:
                    specs = [specs]
                return specs

        # create a temporary file and store the spec there since
        # `parse_requirements` requires a file
        with NamedTemporaryFile(mode='w+', suffix='pysolve') as f:
            f.write(spec)
            f.flush()
            parsed = parse_requirements(f.name, session=f.name)
            dependency = [Dependency(x.name, _get_pip_spec(x.req)) for x in parsed].pop()

        return dependency

    def parse(self, specs):
        """Parse specs."""
        return [self._parse_python(s) for s in specs]

    @staticmethod
    def compose(deps):
        """Compose deps."""
        return DependencyParser.compose_sep(deps, ',')

    @staticmethod
    def restrict_versions(deps):
        """Not implemented."""
        return deps  # TODO


class NpmDependencyParser(DependencyParser):
    """NPM Dependency parsing."""

    @staticmethod
    def _parse_npm_tokens(spec):
        """Parse npm tokens."""
        for token in Tokens.operators:
            if token in spec:
                return token, spec.split(token)[1]
        return spec,

    def _parse_npm(self, name, spec):
        """Parse NPM specification of a single dependency.

        :param name: str
        :param spec: str
        :return: Dependency
        """
        specs = check_output(['/usr/bin/semver-ranger', spec], universal_newlines=True).strip()
        if specs == 'null':
            logger.info("invalid version specification for %s = %s", name, spec)
            return None

        ret = []
        for s in specs.split('||'):
            if ' ' in s:
                spaced = s.split(' ')
                assert len(spaced) == 2
                left, right = spaced
                ret.append([self._parse_npm_tokens(left), self._parse_npm_tokens(right)])
            elif s == '*':
                ret.append(('>=', '0.0.0'))
            else:
                ret.append(self._parse_npm_tokens(s))

        return Dependency(name, ret)

    def parse(self, specs):
        """Transform list of dependencies (strings) to list of Dependency."""
        deps = []
        for spec in specs:
            name, ver = spec.split(' ', 1)
            parsed = self._parse_npm(name, ver)
            if parsed:
                deps.append(parsed)

        return deps

    @staticmethod
    def compose(deps):
        """Oposite of parse()."""
        return DependencyParser.compose_sep(deps, ' ')

    @staticmethod
    def restrict_versions(deps):
        """From list of semver ranges select only the most restricting ones for each operator.

        :param deps:  list of Dependency(), example:
                           [node [('>=', '0.6.0')], node [('<', '1.0.0')], node [('>=', '0.8.0')]]
        :return: list of Dependency() with only the most restrictive versions, example:
                           [node [('<', '1.0.0')], node [('>=', '0.8.0')]]
        """
        # list to dict
        # {
        #    'node' : {
        #            '>=': ['0.8.0', '0.6.0'],
        #            '<': ['1.0.0']
        #        }
        #  }
        dps_dict = defaultdict(dict)
        for dp in deps:
            if dp.name not in dps_dict:
                dps_dict[dp.name] = defaultdict(list)
            for spec in dp.spec:
                if len(spec) != 2:
                    continue
                operator, version = spec
                dps_dict[dp.name][operator].append(version)

        # select only the most restrictive versions
        result = []
        for name, version_spec_dict in dps_dict.items():
            specs = []
            for operator, versions in version_spec_dict.items():
                if operator in ['>', '>=']:  # select highest version
                    version = sorted(versions, key=cmp_to_key(compare_version))[-1]
                elif operator in ['<', '<=']:  # select lowest version
                    version = sorted(versions, key=cmp_to_key(compare_version))[0]
                specs.append((operator, version))
            # dict back to list
            result.append(Dependency(name, specs))

        return result


RubyGemsDependencyParser = NpmDependencyParser


class OSSIndexDependencyParser(NpmDependencyParser):
    """Parse OSS Index version specification."""

    def _parse_npm(self, name, spec):
        """Parse OSS Index version specification. It's similar to NPM semver, with few tweaks."""
        # sometimes there's '|' instead of  '||', but the meaning seems to be the same
        spec = spec.replace(' | ', ' || ')
        # remove superfluous brackets
        spec = spec.replace('(', '').replace(')', '')
        return super()._parse_npm(name, spec)


class NugetDependencyParser(object):
    """Nuget version specification parsing."""

    def parse(self, specs):
        """Transform list of dependencies (strings) to list of Dependency.

        https://docs.microsoft.com/en-us/nuget/create-packages/dependency-versions#version-ranges
        :param specs:  list of dependencies (strings)
        :return: list of Dependency
        """
        deps = []
        for spec in specs:
            name, version_range = spec.split(' ', 1)

            # 1.0 -> 1.0≤x
            if re.search('[,()\[\]]', version_range) is None:
                dep = Dependency(name, [('>=', version_range)])
            # [1.0,2.0] -> 1.0≤x≤2.0
            elif re.fullmatch(r'\[(.+),(.+)\]', version_range):
                m = re.fullmatch(r'\[(.+),(.+)\]', version_range)
                dep = Dependency(name, [[('>=', m.group(1)), ('<=', m.group(2))]])
            # (1.0,2.0) -> 1.0<x<2.0
            elif re.fullmatch(r'\((.+),(.+)\)', version_range):
                m = re.fullmatch(r'\((.+),(.+)\)', version_range)
                dep = Dependency(name, [[('>', m.group(1)), ('<', m.group(2))]])
            # The following one is not in specification,
            # so we can just guess what was the intention.
            # Seen in NLog:5.0.0-beta08 dependencies
            # [1.0, ) -> 1.0≤x
            elif re.fullmatch(r'\[(.+), \)', version_range):
                m = re.fullmatch(r'\[(.+), \)', version_range)
                dep = Dependency(name, [('>=', m.group(1))])
            # [1.0,2.0) -> 1.0≤x<2.0
            elif re.fullmatch(r'\[(.+),(.+)\)', version_range):
                m = re.fullmatch(r'\[(.+),(.+)\)', version_range)
                dep = Dependency(name, [[('>=', m.group(1)), ('<', m.group(2))]])
            # (1.0,) -> 1.0<x
            elif re.fullmatch(r'\((.+),\)', version_range):
                m = re.fullmatch(r'\((.+),\)', version_range)
                dep = Dependency(name, [('>', m.group(1))])
            # [1.0] -> x==1.0
            elif re.fullmatch(r'\[(.+)\]', version_range):
                m = re.fullmatch(r'\[(.+)\]', version_range)
                dep = Dependency(name, [('==', m.group(1))])
            # (,1.0] -> x≤1.0
            elif re.fullmatch(r'\(,(.+)\]', version_range):
                m = re.fullmatch(r'\(,(.+)\]', version_range)
                dep = Dependency(name, [('<=', m.group(1))])
            # (,1.0) -> x<1.0
            elif re.fullmatch(r'\(,(.+)\)', version_range):
                m = re.fullmatch(r'\(,(.+)\)', version_range)
                dep = Dependency(name, [('<', m.group(1))])
            elif re.fullmatch(r'\((.+)\)', version_range):
                raise ValueError("invalid version range %r" % version_range)

            deps.append(dep)

        return deps


class NoOpDependencyParser(DependencyParser):
    """Dummy dependency parser for ecosystems that don't support version ranges."""

    def parse(self, specs):
        """Transform list of dependencies (strings) to list of Dependency."""
        return [Dependency(*x.split(' ')) for x in specs]

    @staticmethod
    def compose(deps):
        """Opposite of parse()."""
        return DependencyParser.compose_sep(deps, ' ')

    @staticmethod
    def restrict_versions(deps):
        """Not implemented."""
        return deps


class GolangDependencyParser(DependencyParser):
    """Dependency parser for Golang."""

    def parse(self, specs):
        """Transform list of dependencies (strings) to list of Dependency."""
        dependencies = []
        for spec in specs:
            spec_list = spec.split(' ')
            if len(spec_list) > 1:
                dependencies.append(Dependency(spec_list[0], spec_list[1]))
            else:
                dependencies.append(Dependency(spec_list[0], ''))
        return dependencies

    @staticmethod
    def compose(deps):
        """Opposite of parse()."""
        return DependencyParser.compose_sep(deps, ' ')

    @staticmethod
    def restrict_versions(deps):
        """Not implemented."""
        return deps


class Solver(object):
    """Base class for resolving dependencies."""

    def __init__(self, ecosystem, dep_parser=None, fetcher=None, highest_dependency_version=True):
        """Initialize instance."""
        self.ecosystem = ecosystem
        self._dependency_parser = dep_parser
        self._release_fetcher = fetcher
        self._highest_dependency_version = highest_dependency_version

    @property
    def dependency_parser(self):
        """Return DependencyParser instance used by this solver."""
        return self._dependency_parser

    @property
    def release_fetcher(self):
        """Return ReleasesFetcher instance used by this solver."""
        return self._release_fetcher

    def solve(self, dependencies, graceful=True, all_versions=False):
        """Solve `dependencies` against upstream repository.

        :param dependencies: List, List of dependencies in native format
        :param graceful: bool, Print info output to stdout
        :param all_versions: bool, Return all matched versions instead of the latest
        :return: Dict[str, str], Matched versions
        """
        solved = {}
        for dep in self.dependency_parser.parse(dependencies):
            logger.debug("Fetching releases for: {}".format(dep))

            name, releases = self.release_fetcher.fetch_releases(dep.name)

            if name in solved:
                raise SolverException("Dependency: {} is listed multiple times".format(name))

            if not releases:
                if graceful:
                    logger.info("No releases found for: %s", dep.name)
                else:
                    raise SolverException("No releases found for: {}".format(dep.name))

            matching = sorted([release
                               for release in releases
                               if release in dep], key=cmp_to_key(compare_version))

            logger.debug("  matching:\n   {}".format(matching))

            if all_versions:
                solved[name] = matching
            else:
                if not matching:
                    solved[name] = None
                else:
                    if self._highest_dependency_version:
                        solved[name] = matching[-1]
                    else:
                        solved[name] = matching[0]

        return solved


class PypiSolver(Solver):
    """Pypi dependencies solver."""

    def __init__(self, ecosystem, parser=None, fetcher=None):
        """Initialize instance."""
        super(PypiSolver, self).__init__(ecosystem,
                                         parser or PypiDependencyParser(),
                                         fetcher or PypiReleasesFetcher(ecosystem))


class NpmSolver(Solver):
    """Npm dependencies solver."""

    def __init__(self, ecosystem, parser=None, fetcher=None):
        """Initialize instance."""
        super(NpmSolver, self).__init__(ecosystem,
                                        parser or NpmDependencyParser(),
                                        fetcher or NpmReleasesFetcher(ecosystem))


class RubyGemsSolver(Solver):
    """Rubygems dependencies solver."""

    def __init__(self, ecosystem, parser=None, fetcher=None):
        """Initialize instance."""
        super(RubyGemsSolver, self).__init__(ecosystem,
                                             parser or RubyGemsDependencyParser(),
                                             fetcher or RubyGemsReleasesFetcher(ecosystem))


class NugetSolver(Solver):
    """Nuget dependencies solver.

    Nuget is a bit specific because it by default resolves version specs to lowest possible version.
    https://docs.microsoft.com/en-us/nuget/release-notes/nuget-2.8#-dependencyversion-switch
    """

    def __init__(self, ecosystem, parser=None, fetcher=None):
        """Initialize instance."""
        super(NugetSolver, self).__init__(ecosystem,
                                          parser or NugetDependencyParser(),
                                          fetcher or NugetReleasesFetcher(ecosystem),
                                          highest_dependency_version=False)


class MavenManualSolver(Solver):
    """Use this only if you need to resolve all versions or use specific DependencyParser.

    Otherwise use MavenSolver (below).
    """

    def __init__(self, ecosystem, parser, fetcher=None):
        """Initialize instance."""
        super().__init__(ecosystem,
                         parser,
                         fetcher or MavenReleasesFetcher(ecosystem))


class GolangSolver(Solver):
    """Golang dependencies solver."""

    def __init__(self, ecosystem, parser=None, fetcher=None):
        """Initialize instance."""
        super(GolangSolver, self).__init__(ecosystem,
                                           parser or GolangDependencyParser(),
                                           fetcher or GolangReleasesFetcher(ecosystem))

    def solve(self, dependencies):
        """Solve `dependencies` against upstream repository."""
        result = {}
        for dependency in self.dependency_parser.parse(dependencies):
            if dependency.spec:
                result[dependency.name] = dependency.spec
            else:
                version = self.release_fetcher.fetch_releases(dependency.name)[1][0]
                result[dependency.name] = version
        return result


class MavenSolver(object):
    """Doesn't inherit from Solver, because we don't use its solve().

    We also don't need a DependencyParser nor a ReleasesFetcher for Maven.
    'mvn versions:resolve-ranges' does all the dirty work for us.
    Resolves only to one version, so if you need solve(all_versions=True), use MavenManualSolver
    """

    @staticmethod
    def _generate_pom_xml(to_solve):
        """Create pom.xml with dependencies from to_solve.

        And run 'mvn versions:resolve-ranges',
        which resolves the version ranges (overwrites the pom.xml).

        :param to_solve: {"groupId:artifactId": "version-range"}
        """
        project = etree.Element('project')
        etree.SubElement(project, 'modelVersion').text = '4.0.0'
        etree.SubElement(project, 'groupId').text = 'foo.bar.baz'
        etree.SubElement(project, 'artifactId').text = 'testing'
        etree.SubElement(project, 'version').text = '1.0.0'
        dependencies = etree.SubElement(project, 'dependencies')
        for name, version_range in to_solve.items():
            group_id, artifact_id = name.rstrip(':').split(':')
            dependency = etree.SubElement(dependencies, 'dependency')
            etree.SubElement(dependency, 'groupId').text = group_id
            etree.SubElement(dependency, 'artifactId').text = artifact_id
            etree.SubElement(dependency, 'version').text = version_range
        with open('pom.xml', 'wb') as pom:
            pom.write(etree.tostring(project, xml_declaration=True, pretty_print=True))
        TimedCommand.get_command_output(['mvn', 'versions:resolve-ranges'], graceful=False)

    @staticmethod
    def _dependencies_from_pom_xml():
        """Extract dependencies from pom.xml in current directory.

        :return: {"groupId:artifactId": "version"}
        """
        solved = {}
        with open('pom.xml') as r:
            pom_dict = anymarkup.parse(r.read())
        dependencies = pom_dict.get('project', {}).get('dependencies', {}).get('dependency', [])
        if not isinstance(dependencies, list):
            dependencies = [dependencies]
        for dependency in dependencies:
            name = "{}:{}".format(dependency['groupId'], dependency['artifactId'])
            solved[name] = dependency['version']
        return solved

    @staticmethod
    def _resolve_versions(to_solve):
        """Resolve version ranges in to_solve.

        :param to_solve: {"groupId:artifactId": "version-range"}
        :return: {"groupId:artifactId": "version"}
        """
        if not to_solve:
            return {}
        with tempdir() as tmpdir:
            with cwd(tmpdir):
                MavenSolver._generate_pom_xml(to_solve)
                return MavenSolver._dependencies_from_pom_xml()

    @staticmethod
    def is_version_range(ver_spec):
        """Check whether ver_spec contains version range."""
        # http://maven.apache.org/enforcer/enforcer-rules/versionRanges.html
        return re.search('[,()\[\]]', ver_spec) is not None

    def solve(self, dependencies):
        """Solve version ranges in dependencies."""
        already_solved = {}
        to_solve = {}
        for dependency in dependencies:
            name, ver_spec = dependency.split(' ', 1)
            if not self.is_version_range(ver_spec):
                already_solved[name] = ver_spec
            else:
                to_solve[name] = ver_spec
        result = already_solved.copy()
        result.update(self._resolve_versions(to_solve))
        return result


def get_ecosystem_solver(ecosystem, with_parser=None, with_fetcher=None):
    """Get Solver subclass instance for particular ecosystem.

    :param ecosystem: Ecosystem
    :param with_parser: DependencyParser instance
    :param with_fetcher: ReleasesFetcher instance
    :return: Solver
    """
    if ecosystem.is_backed_by(EcosystemBackend.maven):
        if with_parser is None:
            return MavenSolver()
        else:
            return MavenManualSolver(ecosystem, with_parser, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.npm):
        return NpmSolver(ecosystem, with_parser, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.pypi):
        return PypiSolver(ecosystem, with_parser, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
        return RubyGemsSolver(ecosystem, with_parser, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.nuget):
        return NugetSolver(ecosystem, with_parser, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.scm):
        return GolangSolver(ecosystem, with_parser, with_fetcher)

    raise ValueError('Unknown ecosystem: {}'.format(ecosystem.name))


def get_ecosystem_parser(ecosystem):
    """Get DependencyParser subclass instance for particular ecosystem."""
    if ecosystem.is_backed_by(EcosystemBackend.maven):
        return NoOpDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.npm):
        return NpmDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.pypi):
        return PypiDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
        return RubyGemsDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.nuget):
        return NugetDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.scm):
        return GolangDependencyParser()

    raise ValueError('Unknown ecosystem: {}'.format(ecosystem.name))
