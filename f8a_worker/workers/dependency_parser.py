"""
Output: TBD

"""

from f8a_worker.base import BaseTask
from f8a_worker.errors import TaskError
from f8a_worker.utils import TimedCommand, cwd, MavenCoordinates, add_maven_coords_to_set
from f8a_worker.process import Git
from tempfile import TemporaryDirectory
from pathlib import Path
import re


class GithubDependencyTreeTask(BaseTask):
    """Finds out direct and indirect dependencies from a given github repository."""

    _analysis_name = 'dependency_tree'
    
    def execute(self, arguments=None):
        """Main execute method """
        self._strict_assert(arguments.get('github_repo'))
        self._strict_assert(arguments.get('github_sha'))
        self._strict_assert(arguments.get('email_ids'))
        github_repo = arguments.get('github_repo')
        github_sha = arguments.get('github_sha')
        dependencies = list(GithubDependencyTreeTask.extract_dependencies(github_repo, github_sha))
        return {"dependencies": dependencies}

    @staticmethod
    def extract_dependencies(github_repo, github_sha):

        """Extract the dependencies information.

           Currently assuming repository is maven repository.
        """

        with TemporaryDirectory() as workdir:
            repo = Git.clone(url=github_repo, path=workdir, timeout=3600)
            repo.reset(revision=github_sha, hard=True)
            with cwd(repo.repo_path):
                cmd = ["mvn", "org.apache.maven.plugins:maven-dependency-plugin:3.0.2:tree",
                       "-DoutputType=dot",
                       "-DoutputFile={filename}".format(
                           filename=Path.cwd().joinpath("dependency-tree.txt")),
                       "-DappendOutput=true"]
                timed_cmd = TimedCommand(cmd)
                status, output, error = timed_cmd.run(timeout=3600)
                if status != 0 or not Path("dependency-tree.txt").is_file():
                    raise TaskError(error)
                with open("dependency-tree.txt") as f:
                    return GithubDependencyTreeTask.parse_maven_dependency_tree(f.readlines())

    @staticmethod
    def parse_maven_dependency_tree(dependency_tree):

        """Parses the dot representation of maven dependency tree.

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
