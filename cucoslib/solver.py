from collections import defaultdict
from functools import cmp_to_key
import logging
from pip.req.req_file import parse_requirements
from requests import get
from xmlrpc.client import ServerProxy
from subprocess import check_output
from tempfile import NamedTemporaryFile

from cucoslib.enums import EcosystemBackend
from cucoslib.models import Analysis, Ecosystem, Package, Version


logger = logging.getLogger(__name__)


class SolverException(Exception):
    pass


class Tokens(object):
    """ Comparison token representation """
    operators = ['>=', '<=', '==', '>', '<', '=', '!=']
    (GTE, LTE, EQ1, GT, LT, EQ2, NEQ) = range(len(operators))


def compare_version(a, b):
    """
    Compare two version strings

    :param a: str
    :param b: str
    :return: -1 / 0 / 1
    """

    def _range(q):
        """
        Convert a version string to array of integers:
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
        """
        Append `num_zeros` zeros to a copy of `x` and return it

        :param x: List[int]
        :param num_zeros: int
        :return: List[int]
        """
        nx = list(x)
        for _ in range(num_zeros):
            nx.append(0)
        return nx

    def _cardinal(x, y):
        """
        Make both input lists be of same cardinality

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
    def __init__(self, ecosystem):
        self._ecosystem = ecosystem

    @property
    def ecosystem(self):
        return self._ecosystem

    def fetch_releases(self, package):
        return None, None


class PypiReleasesFetcher(ReleasesFetcher):
    def __init__(self, ecosystem):
        super(PypiReleasesFetcher, self).__init__(ecosystem)
        self._rpc = ServerProxy(self.ecosystem.fetch_url)

    def _search_package_name(self, package):
        """
        Case insensitive search

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
        """ XML-RPC API Documentation: https://wiki.python.org/moin/PyPIXmlRpc

            Signature: package_releases(package_name, show_hidden=False)
        """
        if not package:
            raise ValueError("package")

        releases = self._rpc.package_releases(package, True)
        if not releases:
            # if nothing was found then do case-insensitive search
            return self.fetch_releases(self._search_package_name(package))

        return package, releases


class NpmReleasesFetcher(ReleasesFetcher):
    def __init__(self, ecosystem):
        super(NpmReleasesFetcher, self).__init__(ecosystem)

    def fetch_releases(self, package):
        """
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
    def __init__(self, ecosystem):
        super(RubyGemsReleasesFetcher, self).__init__(ecosystem)

    def _search_package_name(self, package):
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
        """
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


class CucosReleasesFetcher(ReleasesFetcher):
    def __init__(self, ecosystem, database):
        super(CucosReleasesFetcher, self).__init__(ecosystem)
        self.database = database

    def fetch_releases(self, package):
        """
        Fetch analysed versions for specific ecosystem + package from cucos
        """
        query = self.database.query(Version).\
            join(Analysis).join(Package).join(Ecosystem).\
            filter(Package.name == package,
                   Ecosystem.name == self.ecosystem.name,
                   Analysis.finished_at.isnot(None))
        versions = {v.identifier for v in query}
        return package, list(sorted(versions, key=cmp_to_key(compare_version)))


class Dependency(object):
    def __init__(self, name, spec):
        self._name = name
        self._spec = spec

    @property
    def name(self):
        return self._name

    @property
    def spec(self):
        return self._spec

    def __contains__(self, item):
        return self.check(item)

    def __repr__(self):
        return "{} {}".format(self.name, self.spec)

    def __eq__(self, other):
        return self.name == other.name and self.spec == other.spec

    def check(self, version):
        """
        Check if `version` fits into our dependency specification

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

        results, intermediaries = False, False
        for spec in self.spec:
            if isinstance(spec, list):
                intermediary = True
                for sub in spec:
                    intermediary &= _compare_spec(sub)
                intermediaries |= intermediary
            elif isinstance(spec, tuple):
                results |= _compare_spec(spec)

        return results or intermediaries


class DependencyParser(object):
    def parse(self, specs):
        pass

    @staticmethod
    def compose_sep(deps, separator):
        """
        Opposite of parse()
        :param deps: list of Dependency()
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
    def _parse_python(self, spec):
        """
        Parse PyPI specification of a single dependency

        :param spec: str, for example "Django>=1.5,<1.8"
        :return:
        """
        def _get_pip_spec(requirements):
            "In Pip 8+ there's no `specs` field and we have to dig the information from the `specifier` field"
            if hasattr(requirements, 'specs'):
                return requirements.specs
            elif hasattr(requirements, 'specifier'):
                return [(spec.operator, spec.version) for spec in requirements.specifier]

        # create a temporary file and store the spec there since
        # `parse_requirements` requires a file
        with NamedTemporaryFile(mode='w+', suffix='pysolve') as f:
            f.write(spec)
            f.flush()
            parsed = parse_requirements(f.name, session=f.name)
            dependency = [Dependency(x.name, _get_pip_spec(x.req) or [('>=', '0.0.0')]) for x in parsed].pop()

        return dependency

    def parse(self, specs):
        deps = []
        for s in specs:
            deps.append(self._parse_python(s))

        return deps

    @staticmethod
    def compose(deps):
        return DependencyParser.compose_sep(deps, ',')

    @staticmethod
    def restrict_versions(deps):
        return deps  # TODO


class NpmDependencyParser(DependencyParser):
    @staticmethod
    def _parse_npm_tokens(spec):
        for token in Tokens.operators:
            if token in spec:
                return token, spec.split(token)[1]
        return spec,

    def _parse_npm(self, name, spec):
        """
        Parse NPM specification of a single dependency

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
        deps = []
        for spec in specs:
            name, ver = spec.split(' ', 1)
            parsed = self._parse_npm(name, ver)
            if parsed:
                deps.append(parsed)

        return deps

    @staticmethod
    def compose(deps):
        return DependencyParser.compose_sep(deps, ' ')

    @staticmethod
    def restrict_versions(deps):
        """
        From list of semver ranges select only the most restricting ones for each operator.

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


class NoOpDependencyParser(DependencyParser):
    """
    Dummy dependency parser for ecosystems that don't support version ranges.
    """
    def parse(self, specs):
        return [Dependency(*x.split(' ')) for x in specs]

    @staticmethod
    def compose(deps):
        return DependencyParser.compose_sep(deps, ' ')

    @staticmethod
    def restrict_versions(deps):
        return deps


class Solver(object):
    def __init__(self, ecosystem, dep_parser=None, fetcher=None):
        self.ecosystem = ecosystem
        self._dependency_parser = dep_parser
        self._release_fetcher = fetcher

    @property
    def dependency_parser(self):
        return self._dependency_parser

    @property
    def release_fetcher(self):
        return self._release_fetcher

    def solve(self, dependencies, graceful=True, all_versions=False):
        """
        Solve `dependencies` against upstream repository

        :param dependencies: List, List of dependencies in native format
        :param graceful: bool, Print info output to stdout
        :param all_versions: bool, Return all matched versions instead of the latest
        :return: Dict[str, str], Matched versions
        """

        solved = {}
        for dep in self.dependency_parser.parse(dependencies):
            logger.info("Fetching releases for: {}".format(dep))

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

            logger.info("  matching:\n   {}".format(matching))

            if all_versions:
                solved[name] = matching
            else:
                solved[name] = matching.pop() if matching else None

        return solved


class PypiSolver(Solver):
    def __init__(self, ecosystem, fetcher=None):
        super(PypiSolver, self).__init__(ecosystem,
                                         PypiDependencyParser(),
                                         fetcher or PypiReleasesFetcher(ecosystem))


class NpmSolver(Solver):
    def __init__(self, ecosystem, fetcher=None):
        super(NpmSolver, self).__init__(ecosystem,
                                        NpmDependencyParser(),
                                        fetcher or NpmReleasesFetcher(ecosystem))


class RubyGemsSolver(Solver):
    def __init__(self, ecosystem, fetcher=None):
        super(RubyGemsSolver, self).__init__(ecosystem,
                                             RubyGemsDependencyParser(),
                                             fetcher or RubyGemsReleasesFetcher(ecosystem))


def get_ecosystem_solver(ecosystem, with_fetcher=None):
    """
    Get `Solver` instance for particular ecosystem

    :param ecosystem: Ecosystem
    :return: Solver
    """
    if ecosystem.is_backed_by(EcosystemBackend.pypi):
        return PypiSolver(ecosystem, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.npm):
        return NpmSolver(ecosystem, with_fetcher)
    elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
        return RubyGemsSolver(ecosystem, with_fetcher)

    raise ValueError('Unknown ecosystem: {}'.format(ecosystem.name))


def get_ecosystem_parser(ecosystem):
    if ecosystem.is_backed_by(EcosystemBackend.pypi):
        return PypiDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.npm):
        return NpmDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.rubygems):
        return RubyGemsDependencyParser()
    elif ecosystem.is_backed_by(EcosystemBackend.maven):
        return NoOpDependencyParser()

    raise ValueError('Unknown ecosystem: {}'.format(ecosystem.name))
