"""Extracts ecosystem specific information and transforms it to a common scheme.

Scans the cache path for manifest files (package.json, setup.py, *.gemspec,
*.jar, Makefile etc.) to extract meta data and transform it a common scheme.

Output: information such as: homepage, bug tracking, dependencies

See [../../mercator/README.md](mercator/README.md)

sample output:
{'author': 'Aaron Patterson <aaronp@rubyforge.org>, Mike Dalessio '
           '<mike.dalessio@gmail.com>, Yoko Harada <yokolet@gmail.com>',
 'declared_license': 'MIT',
 'dependencies': ['mini_portile2 ~>2.0.0.rc2'],
 'description': 'Nokogiri is an HTML, XML, SAX, and Reader parser.',
 'devel_dependencies': ['rdoc ~>4.0',
                        'hoe-bundler >=1.1',
                        'hoe-debugging ~>1.2.1',
                        'hoe ~>3.14'],
 'homepage': 'http://nokogiri.org',
 'name': 'nokogiri',
 'version': '1.6.7.2'}
"""

import os
import json

from f8a_worker.base import BaseTask
from f8a_worker.data_normalizer import DataNormalizer
from f8a_worker.enums import EcosystemBackend
from f8a_worker.object_cache import ObjectCache
from f8a_worker.process import Git
from f8a_worker.schemas import SchemaRef
from f8a_worker.utils import TimedCommand, tempdir


# TODO: we need to unify the output from different ecosystems
class MercatorTask(BaseTask):
    """Collects `Release` specific information from Mercator."""

    _analysis_name = 'metadata'
    _dependency_tree_lock = '_dependency_tree_lock'
    schema_ref = SchemaRef(_analysis_name, '3-2-0')
    _data_normalizer = DataNormalizer()

    def _parse_requires_txt(self, path):
        requires = []
        try:
            with open(path, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line.startswith('['):
                        # the first named ini-like [section] ends the runtime requirements
                        break
                    elif line:
                        requires.append(line)
        except Exception as e:
            self.log.warning('Failed to process "{p}": {e}'.format(p=path, e=str(e)))

        return requires

    def _merge_python_items(self, topdir, data):
        metadata_json = None
        pkg_info = None
        requirements_txt = None

        def get_depth(path):
            return path.rstrip('/').count('/')

        def is_deeper(item1, item2):
            """Return True if item1 is deeper in directory hierarchy than item2."""
            if item1 is None:
                return True
            return get_depth(item1['path']) > get_depth(item2['path'])

        # find outermost PKG_INFO/metadata.json/requirements.txt - there can be
        #  testing ones etc.
        for item in data['items']:
            if item['ecosystem'] == 'Python-Dist' and item['path'].endswith('.json'):
                if is_deeper(metadata_json, item):
                    metadata_json = item
            elif item['ecosystem'] == 'Python-Dist':  # PKG-INFO
                # we prefer PKG_INFO files from .egg-info directories,
                #  since these have the very useful `requires.txt` next to them
                if pkg_info is None:
                    pkg_info = item
                else:
                    pkg_info_in_egg = pkg_info['path'].endswith('.egg-info/PKG-INFO')
                    item_in_egg = item['path'].endswith('.egg-info/PKG-INFO')
                    # rather than one insane condition, we use several less complex ones
                    if pkg_info_in_egg and item_in_egg and is_deeper(pkg_info, item):
                        # if both are in .egg-info, but current pkg_info is deeper
                        pkg_info = item
                    elif item_in_egg and not pkg_info_in_egg:
                        # if item is in .egg-info and current pkg_info is not
                        pkg_info = item
                    elif not (item_in_egg or pkg_info_in_egg) and is_deeper(pkg_info, item):
                        # if none of them are in .egg-info, but current pkg_info is deeper
                        pkg_info = item
            elif item['ecosystem'] == 'Python-RequirementsTXT' and is_deeper(pkg_info, item):
                requirements_txt = item

        if pkg_info:
            self.log.info('Found PKG-INFO at {p}'.format(p=pkg_info['path']))
        if metadata_json:
            self.log.info('Found metadata.json at {p}'.format(p=metadata_json['path']))
        if requirements_txt:
            self.log.info('Found requirements.txt at {p}'.format(p=requirements_txt['path']))

        ret = None
        # figure out if this was packaged as wheel => metadata.json would
        #  have depth of topdir + 2
        if metadata_json and get_depth(metadata_json['path']) == get_depth(topdir) + 2:
            self.log.info('Seems like this is wheel, using metadata.json ...')
            ret = metadata_json
        # figure out if this was packaged as sdist => PKG_INFO would
        #  have depth of topdir + 3 (e.g. requests-2.18.1/requests.egg-info/PKG-INFO)
        #             or topdir + 4 (e.g. pydocstyle-2.0.0/src/pydocstyle.egg-info/PKG-INFO)
        #  (and perhaps there are requires.txt or requirements.txt that we could use)
        # NOTE: for now, we always treat requirements.txt as requires_dist
        elif pkg_info and get_depth(pkg_info['path']) <= get_depth(topdir) + 4:
            self.log.info('Seems like this is sdist or egg, using PKG-INFO ...')
            requires_dist = []
            # in well-made sdists, there are requires.txt next to PKG_INFO
            #  (this is something different that requirements.txt)
            #  TODO: maybe mercator could do this in future
            requires = os.path.join(os.path.dirname(pkg_info['path']), 'requires.txt')
            if os.path.exists(requires):
                self.log.info('Found a "requires.txt" file next to PKG-INFO, going to use it ...')
                requires_dist = self._parse_requires_txt(requires)
            elif requirements_txt:
                self.log.info('No "requires.txt" file found next to PKG-INFO, but requirements.txt'
                              ' found, going to use it')
                # if requires.txt can't be found, try requirements.txt
                requires_dist = requirements_txt['result']['dependencies']
            else:
                self.log.info('Found no usable source of requirements for PKG-INFO :(')
            pkg_info['result']['requires_dist'] = requires_dist
            ret = pkg_info
        elif requirements_txt:
            self.log.info('Only requirements.txt found, going to use it ...')
            requirements_txt['result']['requires_dist'] = \
                requirements_txt['result'].pop('dependencies')
            ret = requirements_txt

        return ret

    def execute(self, arguments):
        """Execute mercator and convert it's output to JSON object."""
        self._strict_assert(arguments.get('ecosystem'))

        if 'url' in arguments:
            # run mercator on a git repo
            return self.run_mercator_on_git_repo(arguments)

        self._strict_assert(arguments.get('name'))
        self._strict_assert(arguments.get('version'))

        # TODO: make this even uglier; looks like we didn't get the abstraction quite right
        #       when we were adding support for Java/Maven.
        if self.storage.get_ecosystem(arguments['ecosystem']).is_backed_by(EcosystemBackend.maven):
            # cache_path now points directly to the pom
            cache_path = ObjectCache.get_from_dict(arguments).get_pom_xml()
        else:
            cache_path = ObjectCache.get_from_dict(arguments).get_extracted_source_tarball()
        return self.run_mercator(arguments, cache_path)

    def run_mercator_on_git_repo(self, arguments):
        self._strict_assert(arguments.get('url'))

        with tempdir() as workdir:
            repo_url = arguments.get('url')
            repo = Git.clone(repo_url, path=workdir, depth=str(1))
            metadata = self.run_mercator(arguments, workdir,
                                         keep_path=True, outermost_only=False, timeout=900)
            if metadata.get('status', None) != 'success':
                self.log.error('Mercator failed on %s', repo_url)
                return None

            # add some auxiliary information so we can later find the manifest file
            head = repo.rev_parse(['HEAD'])[0]
            for detail in metadata['details']:
                path = detail['path'][len(workdir):]
                # path should look like this:
                # <git-sha1>/path/to/manifest.file
                detail['path'] = head + path

            return metadata

    def run_mercator(self, arguments, cache_path,
                     keep_path=False, outermost_only=True, timeout=300, resolve_poms=True):
        result_data = {'status': 'unknown',
                       'summary': [],
                       'details': []}
        mercator_target = arguments.get('cache_sources_path', cache_path)

        if arguments['ecosystem'] == 'go':
            # no Go support in Mercator-go yet, we handle it separately here
            tc = TimedCommand(['gofedlib-cli', '--dependencies-main', '--dependencies-packages',
                               '--dependencies-test', '--skip-errors',
                               mercator_target])
            status, data, err = tc.run(timeout=timeout)
        else:
            tc = TimedCommand(['mercator', mercator_target])
            update_env = {'MERCATOR_JAVA_RESOLVE_POMS': 'true'} if resolve_poms else {}
            status, data, err = tc.run(timeout=timeout,
                                       is_json=True,
                                       update_env=update_env)
        if status != 0:
            self.log.error(err)
            result_data['status'] = 'error'
            return result_data
        ecosystem_object = self.storage.get_ecosystem(arguments['ecosystem'])
        if ecosystem_object.is_backed_by(EcosystemBackend.pypi):
            # TODO: attempt static setup.py parsing with mercator
            items = [self._merge_python_items(mercator_target, data)]
        elif arguments['ecosystem'] == 'go':
            result = {'result': json.loads(data[0])}
            # data normalized expects this
            result['ecosystem'] = 'gofedlib'
            # we only support git now
            result['result']['code_repository'] = {
                'type': 'git',
                'url': 'https://{name}'.format(name=arguments.get('name'))
            }

            result['result']['name'] = arguments.get('name')
            result['result']['version'] = arguments.get('version')
            items = [result]
            main_deps_count = len(result['result'].get('deps-main', []))
            packages_count = len(result['result'].get('deps-packages', []))
            self.log.debug('gofedlib found %i dependencies', main_deps_count + packages_count)
        else:
            if outermost_only:
                # process only root level manifests (or the ones closest to the root level)
                items = self._data_normalizer.get_outermost_items(data.get('items') or [])
            else:
                items = data.get('items') or []
            self.log.debug('mercator found %i projects, outermost %i',
                           len(data), len(items))

            if ecosystem_object.is_backed_by(EcosystemBackend.maven):
                # for maven we download both Jar and POM, we consider POM to be *the*
                #  source of information and don't want to duplicate info by including
                #  data from pom included in artifact (assuming it's included)
                items = [d for d in items if d['ecosystem'].lower() == 'java-pom']

        result_data['details'] = [self._data_normalizer.handle_data(d, keep_path=keep_path)
                                  for d in items]
        result_data['status'] = 'success'
        return result_data
