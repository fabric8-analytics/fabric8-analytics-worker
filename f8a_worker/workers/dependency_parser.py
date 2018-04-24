"""Output: TBD."""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

from f8a_worker.base import BaseTask
from f8a_worker.errors import TaskError
from f8a_worker.process import Git
from f8a_worker.utils import TimedCommand, cwd, add_maven_coords_to_set, peek
from f8a_worker.workers.mercator import MercatorTask


class GithubDependencyTreeTask(BaseTask):
    """Finds out direct and indirect dependencies from a given github repository."""

    _mercator = MercatorTask.create_test_instance(task_name='GithubDependencyTreeTask')

    def execute(self, arguments=None):
        """Task code.

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('github_repo'))
        self._strict_assert(arguments.get('github_sha'))
        self._strict_assert(arguments.get('email_ids'))
        github_repo = arguments.get('github_repo')
        github_sha = arguments.get('github_sha')
        dependencies = list(GithubDependencyTreeTask.extract_dependencies(github_repo, github_sha))
        return {"dependencies": dependencies, "github_repo": github_repo,
                "github_sha": github_sha, "email_ids": arguments.get('email_ids')}

    @staticmethod
    def extract_dependencies(github_repo, github_sha):
        """Extract the dependencies information.

        Currently assuming repository is maven/npm repository.
        """
        with TemporaryDirectory() as workdir:
            repo = Git.clone(url=github_repo, path=workdir, timeout=3600)
            repo.reset(revision=github_sha, hard=True)
            with cwd(repo.repo_path):
                # TODO: Make this task also work for files not present in root directory.

                # First change the package-lock.json to npm-shrinkwrap.json
                GithubDependencyTreeTask.change_package_lock_to_shrinkwrap()

                if peek(Path.cwd().glob("pom.xml")):
                    return GithubDependencyTreeTask.get_maven_dependencies()
                elif peek(Path.cwd().glob("npm-shrinkwrap.json")) \
                        or peek(Path.cwd().glob("package.json")):
                    return GithubDependencyTreeTask.get_npm_dependencies(repo.repo_path)
                else:
                    raise TaskError("Please provide maven or npm repository for scanning!")

    @staticmethod
    def get_maven_dependencies():
        """Get direct and indirect dependencies from pom.xml by using maven dependency tree plugin.

        :return: a list of direct and indirect dependencies
        """
        output_file = Path.cwd() / "dependency-tree.txt"
        cmd = ["mvn", "org.apache.maven.plugins:maven-dependency-plugin:3.0.2:tree",
               "-DoutputType=dot",
               "-DoutputFile={filename}".format(filename=output_file),
               "-DappendOutput=true"]
        timed_cmd = TimedCommand(cmd)
        status, output, _ = timed_cmd.run(timeout=3600)
        if status != 0 or not output_file.is_file():
            # all errors are in stdout, not stderr
            raise TaskError(output)
        with output_file.open() as f:
            return GithubDependencyTreeTask.parse_maven_dependency_tree(f.readlines())

    @staticmethod
    def parse_maven_dependency_tree(dependency_tree):
        """Parse the dot representation of maven dependency tree.

        For available representations of dependency tree see
        http://maven.apache.org/plugins/maven-dependency-plugin/tree-mojo.html#outputType
        """
        dot_file_parser_regex = re.compile('"(.*?)"')
        set_pom_names = set()
        set_package_names = set()
        for line in dependency_tree:
            matching_lines_list = dot_file_parser_regex.findall(line)
            # If there's only one string, it means this a pom name.
            if len(matching_lines_list) == 1:
                # Remove scope from package name. Package name is of the form:
                # <group-id>:<artifact-id>:<packaging>:<?classifier>:<version>:<scope>
                matching_line = matching_lines_list[0].rsplit(':', 1)[0]
                add_maven_coords_to_set(matching_line, set_pom_names)
            else:
                for matching_line in matching_lines_list:
                    matching_line = matching_line.rsplit(':', 1)[0]
                    add_maven_coords_to_set(matching_line, set_package_names)

        # Remove pom names from actual package names.
        return set_package_names.difference(set_pom_names)

    @classmethod
    def get_npm_dependencies(cls, path):
        """Get a list of direct and indirect dependencies from npm-shrinkwrap.

        If there is no npm-shrinkwrap file present then it fall backs to use package.json
        and provides only the list of direct dependencies.

        :param path: path to run the mercator
        :return: list of direct (and indirect) dependencies
        """
        mercator_output = cls._mercator.run_mercator(arguments={"ecosystem": "npm"},
                                                     cache_path=path,
                                                     resolve_poms=False)
        set_package_names = set()
        mercator_output_details = mercator_output['details'][0]
        dependency_tree_lock = mercator_output_details \
            .get('_dependency_tree_lock')

        # Check if there is lock file present
        if dependency_tree_lock:
            dependencies = dependency_tree_lock.get('dependencies')

            for dependency in dependencies:
                transitive_deps = dependency.get('dependencies')
                name = dependency.get('name')
                version = dependency.get('version')
                dev_dependency = dependency.get('dev')
                if not dev_dependency:
                    set_package_names.add("{ecosystem}:{package}:{version}".format(ecosystem="npm",
                                          package=name, version=version))

                if transitive_deps:
                    t_dep = transitive_deps[0]
                    name = t_dep.get('name')
                    version = t_dep.get('version')
                    dev_dependency = dependency.get('dev')
                    if not dev_dependency:
                        set_package_names.add("{ecosystem}:{package}:{version}"
                                              .format(ecosystem="npm", package=name,
                                                      version=version))

        else:
            all_dependencies = mercator_output_details.get('dependencies', [])
            for dependency in all_dependencies:
                name, version = dependency.split()
                set_package_names.add("{ecosystem}:{package}:{version}".format(ecosystem="npm",
                                      package=name, version=version))

        return set_package_names

    @staticmethod
    def change_package_lock_to_shrinkwrap():
        """Rename package-lock.json to npm-shrinkwrap.json.

        For more information about package-lock.json please visit
        https://docs.npmjs.com/files/package-lock.json
        """
        # TODO: Remove this method once mercator has support for package-lock.json

        package_lock_path = Path.cwd() / "package-lock.json"

        if package_lock_path.is_file():
            package_lock_path.rename("npm-shrinkwrap.json")
