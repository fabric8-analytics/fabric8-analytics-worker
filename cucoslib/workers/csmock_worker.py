"""
This is a csmock worker which runs static analysis tools on a given archive.

TODO:
  * What analysis does this run?
  * For what ecosystems?
  * Output sample

Upstream project: https://git.fedorahosted.org/git/csmock.git
Kamil's presentation at Flock 2014: https://kdudka.fedorapeople.org/static-analysis-flock2014.pdf
"""
import json
import os
import sys
import subprocess

from cucoslib.base import BaseTask
from cucoslib.object_cache import ObjectCache


def csmock(args):
    """ call csmock tool with provided args """
    results_prefix = "scan"
    results_filename = "scan-results.js"
    subprocess.check_call(["csmock", "-o", results_prefix] + args)
    result_path = os.path.join(results_prefix, results_filename)
    with open(result_path) as fd:
        return json.load(fd)


class StaticAnalysis(object):
    def __init__(self, archive_path):
        self.archive_path = archive_path

    def analyze(self):
        """
        start analysis on provided archive

        :return: json-deserialized response
        """
        return csmock([
            "-a",                  # use all available tools
            "-c", "true",          # use command `true` to "build" the package
            "--force",             # analyze even if the path is already there
            self.archive_path
        ])


class CsmockTask(BaseTask):
    _analysis_name = 'static_analysis'
    description = "Static analysis of source code"

    def execute(self, arguments):
        """
        task code

        :param arguments: dictionary with task arguments
        :return: {}, results
        """
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        result_data = {
            'status': 'unknown',
            'summary': [],
            'details': []
        }

        source_tarball_path = ObjectCache.get_from_dict(arguments).get_source_tarball()
        sa = StaticAnalysis(source_tarball_path)

        try:
            analysis_result = sa.analyze()

            # make output reproducible - scanning the same
            # input multiple times should always produce
            # the same output
            del analysis_result["scan"]["time-created"]
            del analysis_result["scan"]["time-finished"]
            del analysis_result["scan"]["host"]
            del analysis_result["scan"]["store-results-to"]

            stats = {}
            for defect in analysis_result["defects"]:
                stats.setdefault(defect["checker"], {"count": 0})
                stats[defect["checker"]]["count"] += 1
                try:
                    stats[defect["checker"]]["cwe"] = defect["cwe"]
                except KeyError:
                    pass
            result_data['summary'] = stats
            result_data['status'] = 'success'
            result_data['details'] = analysis_result
        except Exception as ex:
            self.log.error("static analysis was not successful: %r", ex)
            result_data['status'] = 'error'

        return result_data


if __name__ == "__main__":
    s = StaticAnalysis(sys.argv[1])
    print(json.dumps(s.analyze(), indent=2))
