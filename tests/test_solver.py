"""Tests covering code in solver.py."""

import pytest

import datetime
import flexmock
from f8a_worker.models import Analysis, Package, Version
from f8a_worker.solver import\
    (get_ecosystem_solver, Dependency,
     PypiDependencyParser, NpmDependencyParser, OSSIndexDependencyParser, NugetDependencyParser,
     GolangDependencyParser, MavenReleasesFetcher, NpmReleasesFetcher, NugetReleasesFetcher,
     F8aReleasesFetcher, GolangReleasesFetcher, PypiReleasesFetcher)


class TestDependencyParser(object):
    """Tests for DependencyParser subclasses."""

    @pytest.mark.parametrize('args, expected', [
        (["name 1.0"],
         [Dependency("name", [('>=', '1.0')])]),
        (["name (1.0,)"],
         [Dependency("name", [('>', '1.0')])]),
        (["name [1.0]"],
         [Dependency("name", [('==', '1.0')])]),
        (["name (,1.0]"],
         [Dependency("name", [('<=', '1.0')])]),
        (["name (,1.0)"],
         [Dependency("name", [('<', '1.0')])]),
        (["name [1.0,2.0]"],
         [Dependency("name", [[('>=', '1.0'), ('<=', '2.0')]])]),
        (["name (1.0,2.0)"],
         [Dependency("name", [[('>', '1.0'), ('<', '2.0')]])]),
        (["name [1.0,2.0)"],
         [Dependency("name", [[('>=', '1.0'), ('<', '2.0')]])]),
        (["name (1.0)"],
         []),
    ])
    def test_nuget_dependency_parser_parse(self, args, expected):
        """Test NugetDependencyParser.parse()."""
        dep_parser = NugetDependencyParser()
        if not expected:
            with pytest.raises(ValueError):
                dep_parser.parse(args)
        else:
            assert dep_parser.parse(args) == expected

    @pytest.mark.parametrize('args, expected', [
        (["github.com/gorilla/mux"],
         [Dependency("github.com/gorilla/mux", "")]),
        (["github.com/gorilla/mux 3f19343c7d9ce75569b952758bd236af94956061"],
         [Dependency("github.com/gorilla/mux", "3f19343c7d9ce75569b952758bd236af94956061")])
    ])
    def test_golang_dependency_parser_parse(self, args, expected):
        """Test GolangDependencyParser.parse()."""
        dep_parser = GolangDependencyParser()
        assert dep_parser.parse(args) == expected

    @pytest.mark.parametrize('args, expected', [
        (["name >0.6"],
         [Dependency("name", [('>=', '0.7.0')])]),
        (["name ^0.6"],
         [Dependency("name", [[('>=', '0.6.0'), ('<', '0.7.0')]])]),
        (["name >0.6", "node < 1"],
         [Dependency("name", [('>=', '0.7.0')]), Dependency("node", [('<', '1.0.0')])]),
        (["name latest"],
         [Dependency("name", [('>=', '0.0.0')])]),
    ])
    def test_npm_dependency_parser_parse(self, args, expected):
        """Test NpmDependencyParser.parse()."""
        dep_parser = NpmDependencyParser()
        assert dep_parser.parse(args) == expected

    @pytest.mark.parametrize('args, expected', [
        (["name <1.6.17 | (>=2.0.0 <2.0.2)"],
         [Dependency("name", [('<', '1.6.17'), [('>=', '2.0.0'), ('<', '2.0.2')]])]),
    ])
    def test_oss_index_dependency_parser_parse(self, args, expected):
        """Test OSSIndexDependencyParser.parse()."""
        dep_parser = OSSIndexDependencyParser()
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
        """Test NpmDependencyParser.compose()."""
        dep_parser = NpmDependencyParser()
        assert dep_parser.compose(args) == expected

    @pytest.mark.parametrize('args, expected', [
        ([Dependency("name", [('>=', '0.7.0')])],
         [Dependency("name", [('>=', '0.7.0')])]),
        ([Dependency("name", [('>=', '0.7.0'), ('>=', '0.8.0')])],
         [Dependency("name", [('>=', '0.8.0')])]),
        ([Dependency("name", [('>=', '0.8.0')]),
          Dependency("name", [('>=', '0.13.0')]),
          Dependency("name", [('>=', '0.6.0')])],
         [Dependency("name", [('>=', '0.13.0')])]),
        ([Dependency("name", [('<', '1.7.0')]), Dependency("name", [('<', '1.8.0')])],
         [Dependency("name", [('<', '1.7.0')])]),
    ])
    def test_npm_dependency_parser_restrict_versions(self, args, expected):
        """Test NpmDependencyParser.restrict_versions()."""
        dep_parser = NpmDependencyParser()
        assert dep_parser.restrict_versions(args) == expected

    @pytest.mark.parametrize('args, expected', [
        (["name == 1.0"],
         [Dependency("name", [('==', '1.0')])]),
        (["name >= 1.0, <2.0"],
         [Dependency("name", [[('>=', '1.0'), ('<', '2.0')]])]),
    ])
    def test_pypi_dependency_parser_parse(self, args, expected):
        """Test PypiDependencyParser.parse()."""
        dep_parser = PypiDependencyParser()
        parsed = dep_parser.parse(args)
        assert parsed[0].name == expected[0].name
        assert set(parsed[0].spec[0]) == set(expected[0].spec[0])


class TestSolver(object):
    """Tests for Solver subclasses."""

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
        """Test NpmSolver."""
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
        """Test MavenSolver."""
        solver = get_ecosystem_solver(maven)
        solver_result = solver.solve(dependencies)
        assert len(solver_result) == len(dependencies)
        for name, version in solver_result.items():
            assert expected.get(name, '') == version

    def test_pypi_solver(self, pypi):
        """Test PypiSolver."""
        solver = get_ecosystem_solver(pypi)
        deps = ['django == 1.9.10',
                'pymongo >=3.0, <3.2.2',
                'six~=1.7.1',
                'coverage~=3.5.1b1.dev',
                'pyasn1>=0.2.2,~=0.2.2',
                'requests===2.16.2',
                'click==0.*']
        out = solver.solve(deps)
        assert out == {'django': '1.9.10',
                       'pymongo': '3.2.1',
                       'six': '1.7.3',
                       'coverage': '3.5.3',
                       'pyasn1': '0.2.3',
                       'requests': '2.16.2',
                       'click': '0.7'}

    def test_rubygems_solver(self, rubygems):
        """Test RubyGemsSolver."""
        solver = get_ecosystem_solver(rubygems)
        deps = ['hoe <3.4.0',
                'rake-compiler ~>0.9.2']
        out = solver.solve(deps)
        assert out == {'hoe': '3.3.1',
                       'rake-compiler': '0.9.9'}

    def test_nuget_solver(self, nuget):
        """Test NugetSolver."""
        solver = get_ecosystem_solver(nuget)
        deps = ['jQuery [1.4.4, 1.6)',
                'NUnit 3.2.1',
                'NETStandard.Library [1.6.0, )']
        out = solver.solve(deps)
        # nuget resolves to lowest version by default, see
        # https://docs.microsoft.com/en-us/nuget/release-notes/nuget-2.8#-dependencyversion-switch
        assert out == {'jQuery': '1.4.4',
                       'NUnit': '3.2.1',
                       'NETStandard.Library': '1.6.0'}

    @pytest.mark.parametrize('dependencies, expected', [
        ([], {}),
        (['github.com/msrb/mux'],
         {'github.com/msrb/mux': 'bdd5a5a1b0b489d297b73eb62b5f6328df198bfc'}),
        (['github.com/msrb/mux bdd5a5a1b0b489d297b73eb62b5f6328df198bfc'],
         {'github.com/msrb/mux': 'bdd5a5a1b0b489d297b73eb62b5f6328df198bfc'})
    ])
    def test_golang_solver(self, go, dependencies, expected):
        """Test GolangSolver."""
        solver = get_ecosystem_solver(go)
        solver_result = solver.solve(dependencies)
        assert len(solver_result) == len(dependencies)
        for name, version in solver_result.items():
            assert expected.get(name, '') == version, '"{}" "{}" "{}"'.format(
                name, version, expected)


class TestFetcher(object):
    """Tests for ReleasesFetcher subclasses."""

    @pytest.mark.parametrize('package, expected', [
        ('org.apache.flex.blazeds:flex-messaging-core',
         {'4.7.0', '4.7.1', '4.7.2', '4.7.3'})
    ])
    def test_maven_fetcher(self, maven, package, expected):
        """Test MavenReleasesFetcher."""
        f = MavenReleasesFetcher(maven)
        _, releases = f.fetch_releases(package)
        assert set(releases) >= expected

    @pytest.mark.parametrize('package, expected', [
        ('serve-static', {'1.7.1', '1.7.2', '1.13.2'}),
        ('@slicemenice/event-utils', {'1.0.0', '1.0.1', '1.1.0', '1.1.1'}),
        ('somereallydummynonexistentpackage', set())
    ])
    def test_npm_fetcher(self, npm, package, expected):
        """Test NpmReleasesFetcher."""
        f = NpmReleasesFetcher(npm)
        _, releases = f.fetch_releases(package)
        assert set(releases) >= expected

    @pytest.mark.parametrize('package, expected', [
        ('anymarkup', {
            '0.1.0', '0.1.1', '0.2.0', '0.3.0', '0.3.1', '0.4.0',
            '0.4.1', '0.4.2', '0.4.3', '0.5.0', '0.6.0', '0.7.0'
        }),
        ('somereallydummynonexistentpackage', set())
    ])
    def test_pypi_fetcher(self, pypi, package, expected):
        """Test NpmReleasesFetcher."""
        f = PypiReleasesFetcher(pypi)
        _, releases = f.fetch_releases(package)
        assert set(releases) >= expected

    @pytest.mark.parametrize('package, expected', [
        ('AjaxControlToolkit',
         {'4.1.60919', '7.1005.0', '17.1.1'}),
        ('Bootstrap',
         {'2.3.2', '3.3.6', '4.0.0-alpha6'}),
        ('log4net',
         {'1.2.10', '2.0.3', '2.0.8'}),
        ('Microsoft.AspNet.Mvc',
         {'5.0.0', '5.2.0', '5.2.3'}),
        ('NUnit',
         {'2.6.4', '3.0.0', '3.7.1'})
    ])
    def test_nuget_fetcher(self, nuget, package, expected):
        """Test NugetReleasesFetcher."""
        f = NugetReleasesFetcher(nuget)
        _, releases = f.fetch_releases(package)
        assert set(releases) >= expected

    @pytest.mark.parametrize('package, expected', [
        ('github.com/msrb/mux',
         {'bdd5a5a1b0b489d297b73eb62b5f6328df198bfc'}),
        ('github.com/jpopelka/flynn/bootstrap',
         {'2811174335f819551ec3de4f21ce75aa3e97be69'})
    ])
    def test_golang_fetcher(self, go, package, expected):
        """Test GolangReleasesFetcher."""
        f = GolangReleasesFetcher(go)
        _, releases = f.fetch_releases(package)
        assert set(releases) == expected

    def test_f8a_fetcher(self, rdb, npm):
        """Test F8aReleasesFetcher."""
        # create initial dataset
        package = Package(ecosystem=npm, name='f8a')
        rdb.add(package)
        rdb.commit()
        versions = {'0.5.0', '0.5.1', '0.6.0', '0.6.4', '0.7.0', '0.8.0', '0.9.0', '1.0.0', '1.0.5'}
        for v in versions:
            version = Version(package=package, identifier=v)
            rdb.add(version)
            rdb.commit()
            analysis = Analysis(version=version)
            # Fetcher only selects finished analyses
            analysis.finished_at = datetime.datetime.utcnow()
            rdb.add(analysis)
            rdb.commit()

        f = F8aReleasesFetcher(npm, rdb)

        r = f.fetch_releases('f8a')[1]

        # make sure we fetched the same stuff we inserted
        assert set(r) == versions

        # first should be the latest
        assert r.pop() == '1.0.5'

        # try different dependency specs
        s = get_ecosystem_solver(npm, with_fetcher=f)
        assert s.solve(['f8a ^0.5.0'])['f8a'] == '0.5.1'
        assert s.solve(['f8a 0.x.x'])['f8a'] == '0.9.0'
        assert s.solve(['f8a >1.0.0'])['f8a'] == '1.0.5'
        assert s.solve(['f8a ~>0.6.0'])['f8a'] == '0.6.4'

        # check that with `all_versions` we return all the relevant ones
        assert set(s.solve(['f8a >=0.6.0'], all_versions=True)['f8a']) == \
            (versions - {'0.5.0', '0.5.1'})
