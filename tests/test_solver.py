import pytest

import datetime
import flexmock
from f8a_worker.enums import EcosystemBackend
from f8a_worker.models import Analysis, Ecosystem, Package, Version
from f8a_worker.solver import Dependency, NpmDependencyParser,\
    get_ecosystem_solver, CucosReleasesFetcher, NpmReleasesFetcher


@pytest.fixture
def maven(rdb):
    maven = Ecosystem(name='maven', backend=EcosystemBackend.maven,
                      fetch_url='')
    rdb.add(maven)
    rdb.commit()
    return maven


@pytest.fixture
def npm(rdb):
    npm = Ecosystem(name='npm', backend=EcosystemBackend.npm,
                    fetch_url='https://registry.npmjs.org/')
    rdb.add(npm)
    rdb.commit()
    return npm


@pytest.fixture
def pypi(rdb):
    pypi = Ecosystem(name='pypi', backend=EcosystemBackend.pypi,
                     fetch_url='https://pypi.python.org/pypi')
    rdb.add(pypi)
    rdb.commit()
    return pypi


@pytest.fixture
def rubygems(rdb):
    rubygems = Ecosystem(name='rubygems', backend=EcosystemBackend.rubygems,
                         fetch_url='https://rubygems.org/api/v1')
    rdb.add(rubygems)
    rdb.commit()
    return rubygems


class TestSolver(object):
    @pytest.mark.parametrize('args, expected', [
        (["name >0.6"],
         [Dependency("name", [('>=', '0.7.0')])]),
        (["name ^0.6"],
         [Dependency("name", [[('>=', '0.6.0'), ('<', '0.7.0')]])]),
        (["name >0.6", "node < 1"],
         [Dependency("name", [('>=', '0.7.0')]), Dependency("node", [('<', '1.0.0')])]),
    ])
    def test_npm_dependency_parser_parse(self, args, expected):
        dep_parser = NpmDependencyParser()
        assert dep_parser.parse(args) == expected

    @pytest.mark.parametrize('args, expected', [
        ([],
         {}),
        ([Dependency("name", [('>=', '0.7.0')])],
         {"name": ">=0.7.0"}),
        ([Dependency("name", [('>=', '0.6.0'), ('<', '0.7.0')])],
         {"name": ">=0.6.0 <0.7.0"}),
        ([Dependency("name", [('>=', '0.7.0')]), Dependency("node", [('<', '1.0.0')])],
         {"name": ">=0.7.0",
          "node": "<1.0.0"}),
    ])
    def test_npm_dependency_parser_compose(self, args, expected):
        dep_parser = NpmDependencyParser()
        assert dep_parser.compose(args) == expected

    @pytest.mark.parametrize('args, expected', [
        ([Dependency("name", [('>=', '0.7.0')])],
         [Dependency("name", [('>=', '0.7.0')])]),
        ([Dependency("name", [('>=', '0.7.0'), ('>=', '0.8.0')])],
         [Dependency("name", [('>=', '0.8.0')])]),
        ([Dependency("name", [('>=', '0.8.0')]), Dependency("name", [('>=', '0.13.0')]), Dependency("name", [('>=', '0.6.0')])],
         [Dependency("name", [('>=', '0.13.0')])]),
        ([Dependency("name", [('<', '1.7.0')]), Dependency("name", [('<', '1.8.0')])],
         [Dependency("name", [('<', '1.7.0')])]),
    ])
    def test_npm_dependency_parser_restrict_versions(self, args, expected):
        dep_parser = NpmDependencyParser()
        assert dep_parser.restrict_versions(args) == expected

    SERVE_STATIC_VER = ["1.0.0", "1.0.1", "1.0.2", "1.0.3", "1.0.4",
                        "1.1.0",
                        "1.2.0", "1.2.1", "1.2.2", "1.2.3",
                        "1.3.0", "1.3.1", "1.3.2",
                        "1.4.0", "1.4.1", "1.4.2", "1.4.3", "1.4.4",
                        "1.5.0", "1.5.1", "1.5.2", "1.5.3", "1.5.4",
                        "1.6.0", "1.6.1", "1.6.2", "1.6.3", "1.6.4", "1.6.5",
                        "1.7.0", "1.7.1", "1.7.2",
                        "1.8.0", "1.8.1",
                        "1.9.0", "1.9.1", "1.9.2", "1.9.3",
                        "1.10.0", "1.10.1", "1.10.2", "1.10.3",
                        "1.11.0", "1.11.1", "1.11.2",
                        "1.12.0", "1.12.1"]

    # https://semver.npmjs.com
    @pytest.mark.parametrize('semver_string, expected', [
        ('1.2.3', ['1.2.3']),
        ('<1.0.2', ['1.0.0', '1.0.1']),
        ('<=1.0.1', ['1.0.0', '1.0.1']),
        ('>1.11.5', ['1.12.0', '1.12.1']),
        ('>=1.12.0', ['1.12.0', '1.12.1']),
        ('^1.12', ['1.12.0', '1.12.1']),
        ('~1.5.3', ['1.5.3', '1.5.4']),
        ('1.7.1 - 1.8.0', ['1.7.1', '1.7.2', '1.8.0']),
        ('>1.7.1 <1.8.0', ['1.7.2']),
        ('>=1.7.1 <=1.7.2', ['1.7.1', '1.7.2']),
        ('1.0.0 || 1.2.1 || 1.10.1', ['1.0.0', '1.2.1', '1.10.1']),
        ('<1.0.1 || >1.12.0', ['1.0.0', '1.12.1']),
        ('~1.6.5 || >1.11', ['1.6.5', '1.12.0', '1.12.1']),
        ('>=1.6.5 <1.7.0 || >=1.12.0', ['1.6.5', '1.12.0', '1.12.1']),
        ('<1.0.1 || >=1.7.0 <1.7.2', ['1.0.0', '1.7.0', '1.7.1']),
        ('>=1.1.0 <1.1.3 || >1.7.1 <1.8.0 || ~1.11.2', ['1.1.0', '1.7.2', '1.11.2']),
        ('<1.2.0 >1.2.0 || <1.2.1 >1.2.1', []),
    ])
    def test_npm_solver(self, npm, semver_string, expected):
        solver = get_ecosystem_solver(npm)
        name = 'test_name'
        # mock fetched releases to have predictable results
        flexmock(NpmReleasesFetcher, fetch_releases=(name, self.SERVE_STATIC_VER))
        solver_result = solver.solve([name + ' ' + semver_string], all_versions=True)
        # {'name': ['1.0.0', '1.0.1']}
        assert set(solver_result.get(name, [])) == set(expected)

    @pytest.mark.parametrize('dependencies, expected', [
        ([], {}),
        (['group:artifact 1.2.3'],  # not to be resolved
         {'group:artifact': '1.2.3'}),
        # https://mvnrepository.com/artifact/org.webjars.npm/jquery
        (['foo:bar 6.6.6', 'org.webjars.npm:jquery:: [2.2.0,3.1)'],  # mixed
         {'foo:bar': '6.6.6', 'org.webjars.npm:jquery': '3.0.0'})
    ])
    def test_maven_solver(self, maven, dependencies, expected):
        solver = get_ecosystem_solver(maven)
        solver_result = solver.solve(dependencies)
        assert len(solver_result) == len(dependencies)
        for name, version in solver_result.items():
            assert expected.get(name, '') == version

    def test_pypi(self, pypi):
        solver = get_ecosystem_solver(pypi)
        deps = ["pymongo>=3.0,<3.2.2", "celery>3.1.11", "six==1.10.0"]
        out = solver.solve(deps)

        assert len(out) == len(deps)

    def test_rubygems(self, rubygems):
        solver = get_ecosystem_solver(rubygems)
        deps = ["Hoe ~>3.14", "rexicaL >=1.0.5", "raKe-compiler-dock ~>0.4.2",
                "rake-comPiler ~>0.9.2"]
        out = solver.solve(deps)

        assert len(out) == len(deps)

    def test_cucos_fetcher(self, rdb, npm):
        # create initial dataset
        package = Package(ecosystem=npm, name='cucos')
        rdb.add(package)
        rdb.commit()
        versions = {'0.5.0', '0.5.1', '0.6.0', '0.6.4', '0.7.0', '0.8.0', '0.9.0', '1.0.0', '1.0.5'}
        for v in versions:
            version = Version(package=package, identifier=v)
            rdb.add(version)
            rdb.commit()
            analysis = Analysis(version=version)
            # Fetcher only selects finished analyses
            analysis.finished_at = datetime.datetime.now()
            rdb.add(analysis)
            rdb.commit()

        f = CucosReleasesFetcher(npm, rdb)

        r = f.fetch_releases('cucos')[1]

        # make sure we fetched the same stuff we inserted
        assert set(r) == versions

        # first should be the latest
        assert r.pop() == '1.0.5'

        # try different dependency specs
        s = get_ecosystem_solver(npm, f)
        assert s.solve(['cucos ^0.5.0'])['cucos'] == '0.5.1'
        assert s.solve(['cucos 0.x.x'])['cucos'] == '0.9.0'
        assert s.solve(['cucos >1.0.0'])['cucos'] == '1.0.5'
        assert s.solve(['cucos ~>0.6.0'])['cucos'] == '0.6.4'

        # check that with `all_versions` we return all the relevant ones
        assert set(s.solve(['cucos >=0.6.0'], all_versions=True)['cucos']) == \
            (versions - {'0.5.0', '0.5.1'})
