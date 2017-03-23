import functools
import json
import os
import anymarkup
from cucoslib.utils import TimedCommand
from cucoslib.schemas import SchemaRef
from cucoslib.base import BaseTask
from cucoslib.data_normalizer import DataNormalizer
from cucoslib.object_cache import ObjectCache


class CodeMetricsTask(BaseTask):
    _analysis_name = 'code_metrics'
    description = 'Compute various code metrics for a project'
    schema_ref = SchemaRef(_analysis_name, '1-0-0')
    _CLI_TIMEOUT = 3600

    def _run_analyzer(self, command, json_output=True):
        """Run command (analyzer), if a JSON output is expected, parse it

        :param command: command to be run (command with argument vector as array)
        :param json_output: True if output should be parsed
        :return: status, output, error triplet
        """
        self.log.debug("Executing command, timeout={timeout}: {cmd}".format(timeout=self._CLI_TIMEOUT, cmd=command))
        cmd = TimedCommand(command)
        status, output, error = cmd.run(timeout=self._CLI_TIMEOUT)
        self.log.debug("status: %d, output: %s, error: %s", status, output, error)

        if status != 0:
            self.log.warning("Executing command failed, return value: %d, stderr: '%s' ", status, error)

        # Some tools such as complexity-report write zero bytes to output (they are propagated from sources like
        # for npm/glob/7.0.3). This caused failures when pushing results to Postgres as Postgres cannot store
        # null bytes in results. Let's be safe here.
        output = list(line.replace('\\u0000', '\\\\0') for line in output)

        if json_output:
            if output:
                output = "".join(output)
                output = json.loads(output)
            else:
                output = {}

        return status, output, error

    def _get_generic_result(self, source_path):
        """Get core result of CodeMetricsTask task that is based on cloc tool, this output is later enriched with
        output of tools based on languages that were found by cloc

        :param source_path: path to sources where analyzed artefact resists
        :return: tuple where generic information with ecosystem specific dict
        """
        command = ['cloc', '--json', source_path]
        status, output, error = self._run_analyzer(command)

        if status != 0:
            # Let the whole task fail
            raise RuntimeError("Running cloc command failed: '%s'" % error)

        # cloc places generic summary here, we will maintain it in top level so remove misleading key
        header = {
            'total_files': output['header'].pop('n_files'),
            'total_lines': output['header'].pop('n_lines')
        }
        output.pop('header')

        if 'SUM' in output:
            header['blank_lines'] = output['SUM']['blank']
            header['comment_lines'] = output['SUM']['comment']
            header['code_lines'] = output['SUM']['code']
            output.pop('SUM', None)

        # rename to be more precise with naming
        wanted_keys = (('blank', 'blank_lines'),
                       ('code', 'code_lines'),
                       ('comment', 'comment_lines'),
                       ('nFiles', 'files_count'))
        for key in output.keys():
            # filter only language-specific results, leave statistics untouched
            if isinstance(output[key], dict):
                output[key] = DataNormalizer.transform_keys(output[key], wanted_keys)

        return header, output

    @staticmethod
    def _normalize_complexity_report_output(output, source_path):
        """ Normalize complexity_report output
        See https://github.com/escomplex/escomplex/blob/master/README.md#metrics

        :param output: output dict to be normalized
        :param source_path: path to sources that was used
        :return: normalized output
        """
        # For metrics meaning see:
        wanted_keys = (('maintainability', 'project_maintainability'),
                       ('changeCost', 'cost_change'),
                       ('cyclomatic', 'average_cyclomatic_complexity'),
                       ('effort', 'average_halstead_effort'),
                       ('firstOrderDensity', 'first_order_density'),
                       ('loc', 'average_function_lines_of_code'),
                       ('params', 'average_function_parameters_count'),
                       ('reports', 'modules'))
        output = DataNormalizer.transform_keys(output, wanted_keys)

        wanted_module_keys = (('maintainability', 'module_maintainability'),
                              ('dependencies',),
                              ('loc', 'average_function_lines_of_code'),
                              ('path',),
                              ('params', 'average_function_parameters_count'),
                              ('functions',))

        for idx, module in enumerate(output.get('modules', [])):
            output['modules'][idx] = DataNormalizer.transform_keys(module, wanted_module_keys)

            source_path_len = len(source_path) + 1
            if 'path' in module:
                output['modules'][idx]['path'] = module['path'][source_path_len:]

            for fun_idx, function in enumerate(module.get('functions')):
                if 'cyclomaticDensity' in function:
                    function['cyclomatic_density'] = function.pop('cyclomaticDensity')

        return output

    @staticmethod
    def _normalize_javancss_output(output):
        """Parse and normalize JavaNCSS ASCII output

        :param output: output dict to be normalized
        :return: normalized output
        """
        output = output.get('javancss', {})
        result = {
            'functions': {},
            'objects': {},
            'packages': {}
        }

        # The output of JavaNCSS is an XML, which is parsed using anymarkup. This can introduce some pitfalls here
        # if there is found exactly one item of a type. E.g.:
        #
        #  <functions>
        #    <function>...<function/>
        #  <functions>
        #
        # Is parsed as object 'functions' containing *one object* 'function', whereas:
        #
        #  <functions>
        #    <function>...<function/>
        #    <function>...<function/>
        #  <functions>
        #
        # Is parsed as object 'functions' containing a *list of objects* 'function'. Thus the isinstance(.., list)
        # checks.

        # Parse functions section
        if 'functions' in output:
            functions = output['functions']

            wanted_function_keys = (('ccn', 'cyclomatic_complexity'),
                                    ('javadocs',),
                                    ('name',))

            result['functions']['function'] = []
            if 'function' in functions:
                if not isinstance(functions['function'], list):
                    functions['function'] = [functions['function']]

                for function in functions['function']:
                    result['functions']['function'].append(DataNormalizer.transform_keys(function,
                                                                                         wanted_function_keys))

            function_averages = functions.get('function_averages', {})

            result['functions']['average_cyclomatic_complexity'] = function_averages.get('ccn')
            result['functions']['average_javadocs'] = function_averages.get('javadocs')

        # Parse objects section
        if 'objects' in output:
            objects = output['objects']

            wanted_objects_keys = (('classes',),
                                   ('functions',),
                                   ('name',),
                                   ('javadocs',))

            result['objects']['object'] = []
            if 'object' in objects:
                if not isinstance(objects['object'], list):
                    objects['object'] = [objects['object']]

                for obj in objects['object']:
                    result['objects']['object'].append(DataNormalizer.transform_keys(obj,
                                                                                     wanted_objects_keys))

            object_averages = objects.get('averages', {})

            result['objects']['average_classes'] = object_averages.get('classes')
            result['objects']['average_functions'] = object_averages.get('functions')
            result['objects']['average_javadocs'] = object_averages.get('javadocs')

        # Parse packages section
        if 'packages' in output:
            packages = output['packages']

            packages_total = packages.get('total', {})

            result['packages']['classes'] = packages_total.get('classes')
            result['packages']['functions'] = packages_total.get('functions')
            result['packages']['javadoc_lines'] = packages_total.get('javadoc_lines')
            result['packages']['javadocs'] = packages_total.get('javadocs')
            result['packages']['multi_comment_lines'] = packages_total.get('multi_comment_lines')
            result['packages']['single_comment_lines'] = packages_total.get('single_comment_lines')

        return result

    def _normalize_mccabe_output(self, output):
        result = []
        for line in output:
            # NOTE: due to the way print works in python 2 vs python 3, the mccabe under
            #  python 2 returns `(<coords> <name> <complexity>)`, while the python 3
            #  version returns the same without the brackets
            coords, func_name, complexity = line.split()
            result.append({'name': func_name.strip("'"), 'complexity': int(complexity.strip(')'))})

        return result

    def complexity_report(self, source_path):
        """Run complexity_report tool https://www.npmjs.com/package/complexity-report

        :param source_path: path to source codes
        :return: normalized output
        """
        command = ['cr', '--format=json', source_path]
        status, output, error = self._run_analyzer(command)

        if status != 0:
            self.log.warning("Runing complexity report tool failed: %s", error)
            return {}

        if output:
            output = self._normalize_complexity_report_output(output, source_path)
        return output

    def javancss(self, source_path):
        """Run JavaNCSS tool http://www.kclee.de/clemens/java/javancss

        :param source_path: path to source codes
        :return normalized output
        """
        javancss_path = os.path.join(os.environ['JAVANCSS_PATH'], 'bin', 'javancss')
        command = [javancss_path, '-all', '-xml', source_path]
        status, output, error = self._run_analyzer(command, json_output=False)

        if status != 0:
            self.log.warning("JavaNCSS tool reported some errors: %s", error)

        if output:
            output = anymarkup.parse("".join(output))
            output = self._normalize_javancss_output(output)

        return output

    def python_mccabe(self, source_path):
        """Run mccabe tool https://pypi.python.org/pypi/mccabe

        :param source_path: path to source codes
        :return: normalized output
        """
        acc = 'average_cyclomatic_complexity'
        result = {'files': [], acc: 0}
        # we'll compute total average cyclomatic complexity manually based as
        #  <total complexity>/<total number of functions>
        acc_functions = 0
        acc_complexity = 0
        command = ['python3', '-m', 'mccabe']

        # mccabe has to be run on individual files, doesn't work recursively on directories
        for root, dirs, files in os.walk(source_path):
            for f in files:
                if f.endswith('.py'):
                    to_run = command + [os.path.join(root, f)]
                    status, output, error = self._run_analyzer(to_run, json_output=False)
                    if status != 0:
                        self.log.info('Analazying with Py3 failed, trying to analyze with Py2 ...')
                        to_run[0] = 'python2'
                        status, output, error = self._run_analyzer(to_run, json_output=False)
                        if status != 0:
                            self.log.error('Failed to analyze with both Py2 and Py3')
                            continue
                    normalized = self._normalize_mccabe_output(output)

                    # compute file average cyclomatic complexity, add numbers
                    #  to overall package complexity
                    f_complexity = functools.reduce(lambda x, y: x + y['complexity'], normalized, 0)
                    f_functions = len(normalized)
                    f_acc = round(f_complexity / f_functions, 1) if f_functions > 0 else 0
                    acc_complexity += f_complexity
                    acc_functions += f_functions
                    result['files'].append(
                        {'name': os.path.join(root, f)[len(source_path):].strip('/'),
                         'functions': normalized,
                         acc: f_acc})

        result[acc] = round(acc_complexity / acc_functions, 1) if acc_functions > 0 else 0
        return result

    # A table that carries functions that should be called based on language that was found by cloc, keys has to match
    # keys in cloc output. Each handler expect one argument - path to the source where sources sit, the result is
    # a dict. When you write new analyzer handlers, make sure that there are no key collisions with new ones as results
    # are aggregated under "metrics" key.
    # See 'Recognized languages' section at http://cloc.sourceforge.net/
    _LANGUAGE_ANALYZER_HANDLERS = {
        "JavaScript": [
            complexity_report,
        ],
        "Ruby": [],
        "Java": [
            javancss,
        ],
        "Python": [
            python_mccabe,
        ],
        "Go": [],
        "Rust": []
    }

    def execute(self, arguments):
        self._strict_assert(arguments.get('ecosystem'))
        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        source_path = ObjectCache.get_from_dict(arguments).get_sources()
        header, language_stats = self._get_generic_result(source_path)

        for language in language_stats.keys():
            for handler in self._LANGUAGE_ANALYZER_HANDLERS.get(language, []):
                metrics_data = handler(self, source_path)
                if not metrics_data:
                    continue

                if 'metrics' not in language_stats[language]:
                    language_stats[language]['metrics'] = {}

                language_stats[language]['metrics'].update(metrics_data)

        # we don't want to have possibly unique keys and we want to avoid enumerating all languages that are
        # supported by cloc - convert a dict to a list of language-specific entries
        result = {'languages': []}
        for language in language_stats.keys():
            record = language_stats.get(language)
            record['language'] = language
            result['languages'].append(record)

        return {'summary': header, 'status': 'success', 'details': result}
