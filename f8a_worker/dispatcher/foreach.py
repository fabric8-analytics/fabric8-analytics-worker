import logging
from urllib.parse import urlparse
from f8a_worker.utils import MavenCoordinates

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


def iter_unknown_dependencies(storage_pool,node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        aggregated = storage_pool.get('UnknownDependencyFetcherTask')
        postgres = storage_pool.get_connected_storage('BayesianPostgres')
        arguments = []
        for element in aggregated['result']:
            element_list=element.split(":")
            ecosystem = element_list[0]
            name = element_list[1] + ":" + element_list[2]
            version = element_list[3]
            arguments.append(_create_analysis_arguments(ecosystem, name, version))

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except Exception:
        logger.exception("Failed to collect unknown dependencies")
        return []  


def iter_dependencies_analysis(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        postgres = storage_pool.get_connected_storage('BayesianPostgres')
        deps = storage_pool.get('dependency_snapshot').get('details', {}).get('runtime', [])
        arguments = []
        for dep in deps:
            if _is_url_dependency(dep):
                logger.info('skipping URL dependency name "%(ecosystem)s/%(name)s/%(version)s"',
                            dep)
            elif postgres.get_analysis_count(dep['ecosystem'], dep['name'], dep['version']) > 0:
                logger.info('skipping already analysed dependency '
                            '"%(ecosystem)s/%(name)s/%(version)s"', dep)
                continue
            else:
                new_node_args = _create_analysis_arguments(dep['ecosystem'], dep['name'],
                                                           dep['version'])
                if 'recursive_limit' in node_args:
                    new_node_args['recursive_limit'] = node_args['recursive_limit'] - 1
                arguments.append(new_node_args)

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except Exception:
        logger.exception("Failed to collect analysis dependencies")
        return []


def iter_dependencies_stack(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        aggregated = storage_pool.get('AggregatingMercatorTask')
        postgres = storage_pool.get_connected_storage('BayesianPostgres')

        arguments = []
        for result in aggregated["result"]:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']

            for dep in resolved:
                name = dep['package']
                version = dep['version']

                if postgres.get_analysis_count(ecosystem, name, version) > 0:
                    logger.info('skipping already analysed dependency "%s/%s/%s"', ecosystem,
                                name, version)
                    continue

                arguments.append(_create_analysis_arguments(ecosystem, name, version))

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except Exception:
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
    except Exception:
        logger.exception("Failed to collect OSS Index updates")
        return []


def iter_unknown_dependencies(storage_pool, node_args):
    # Be safe here as fatal errors will cause errors in Dispatcher
    try:
        aggregated = storage_pool.get('UnknownDependencyFetcherTask')
        postgres = storage_pool.get_connected_storage('BayesianPostgres')

        arguments = []
        for element in aggregated["result"]:
            ecosystem = element['ecosystem']
            name = element['package']
            version = element['version']

            arguments.append(_create_analysis_arguments(ecosystem, name, version))

        logger.info("Arguments for next flows: %s" % str(arguments))
        return arguments
    except Exception:
        logger.exception("Failed to collect unknown dependencies")
        return []
