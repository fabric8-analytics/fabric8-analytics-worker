import logging
from urllib.parse import urlparse
from cucoslib.utils import MavenCoordinates

logger = logging.getLogger(__name__)


def _create_analysis_arguments(ecosystem, name, version):
    return {
        'ecosystem': ecosystem,
        'name': MavenCoordinates.normalize_str(name) if ecosystem == 'maven' else name,
        'version': version
    }


def _is_url_dependency(dep):
    parsed = urlparse(dep['name'])
    # previously we checked just parsed.scheme, but it marked Maven's groupId:artifactId as URL
    if parsed.scheme and parsed.netloc:
        return True
    elif isinstance(dep['version'], str) and urlparse(dep['version']).scheme:
        return True

    return False


def iter_dependencies_analysis(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        deps = storage_pool.get('dependency_snapshot').get('details', {}).get('runtime', [])

        arguments = []
        for dep in deps:
            if _is_url_dependency(dep):
                logger.info('skipping URL dependency name "%(ecosystem)s/%(name)s/%(version)s"', dep)
            else:
                arguments.append(_create_analysis_arguments(dep['ecosystem'], dep['name'], dep['version']))

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except:
        logger.exception("Failed to collect analysis dependencies")
        return []


def iter_dependencies_stack(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        aggregated = storage_pool.get('AggregatingMercatorTask')

        arguments = []
        for result in aggregated["result"]:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']

            for dep in resolved:
                name = dep['package']
                version = dep['version']
                arguments.append(_create_analysis_arguments(ecosystem, name, version))

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except:
        logger.exception("Failed to collect stack-analysis dependencies")
        return []


def iter_cvedb_updates(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        modified = storage_pool.get('CVEDBSyncTask')['modified']
        # let's force all analyses for now
        for epv in modified:
            epv['force'] = True
        return modified
    except:
        logger.exception("Failed to collect snyk updates")
        return []

