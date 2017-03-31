"""
Extracts ecosystem specific information and transforms it to a common scheme

Scans the cache path for manifest files (package.json, setup.py, *.gemspec, *.jar, Makefile etc.) to extract meta data and transform it a common scheme.

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

from json import loads as to_json
from cucoslib.enums import EcosystemBackend
from cucoslib.utils import TimedCommand
from cucoslib.data_normalizer import DataNormalizer
from cucoslib.schemas import SchemaRef
from cucoslib.base import BaseTask
from cucoslib.object_cache import ObjectCache


# TODO: we need to unify the output from different ecosystems
class MercatorTask(BaseTask):
    _analysis_name = 'metadata'
    _dependency_tree_lock = '_dependency_tree_lock'
    description = 'Collects `Release` specific information from Mercator'
    schema_ref = SchemaRef(_analysis_name, '3-1-0')
    _data_normalizer = DataNormalizer()

    def execute(self, arguments):
        "Execute mercator and convert it's output to JSON object"
        self._strict_assert(arguments.get('ecosystem'))
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

    def run_mercator(self, arguments, cache_path):
        result_data = {'status': 'unknown',
                       'summary': [],
                       'details': []}

        mercator_target = arguments.get('cache_sources_path', cache_path)
        tc = TimedCommand(['mercator', mercator_target])
        status, data, err = tc.run(timeout=300,
                                   is_json=True,
                                   update_env={'MERCATOR_JAVA_RESOLVE_POMS': 'true'})
        if status != 0:
            self.log.error(err)
            result_data['status'] = 'error'
            return result_data
        items = self._data_normalizer.get_outermost_items(data.get('items') or [])
        self.log.debug('mercator found %i projects, outermost %i',
                       len(data), len(items))

        ecosystem_object = self.storage.get_ecosystem(arguments['ecosystem'])
        if ecosystem_object.is_backed_by(EcosystemBackend.maven):
            # for maven we download both Jar and POM, we consider POM to be *the*
            #  source of information and don't want to duplicate info by including
            #  data from pom included in artifact (assuming it's included)
            items = [data for data in items if data['ecosystem'].lower() == 'java-pom']
        result_data['details'] = [self._data_normalizer.handle_data(data) for data in items]

        result_data['status'] = 'success'
        return result_data
