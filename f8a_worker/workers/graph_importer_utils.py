import os
import requests
import logging
import json
import traceback
from f8a_worker.workers.graph_populator import GraphPopulator
from selinon import StoragePool

logger = logging.getLogger(__name__)

# Get Variable Parameters from Environment
GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format(
                           host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost"),
                           port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182"))


class GETS3:
    @staticmethod
    def storage():
        return StoragePool.get_connected_storage('S3Data'), StoragePool.get_connected_storage('S3PackageData')


def read_json_file(filename, bucket_type):
    """Read JSON file from the data source"""

    s3, s3_pkg = GETS3.storage()
    obj = {}
    if bucket_type == "version":
        obj = s3.retrieve_dict(filename)
    elif bucket_type == "package":
        obj = s3_pkg.retrieve_dict(filename)

    return obj


def _first_key_info(first_key, bucket_type):
    obj = {}
    t = read_json_file(first_key, bucket_type)
    obj["dependents_count"] = t.get("dependents_count", '-1')
    obj["package_info"] = t.get("package_info", {})
    obj["latest_version"] = t.get("latest_version", '-1')
    return obj


def _other_key_info(other_keys, bucket_type):
    obj = {"analyses": {}}
    for this_key in other_keys:
        value = read_json_file(this_key, bucket_type)
        this_key = this_key.split("/")[-1]
        if 'success' == value.get('status', ''):
            obj["analyses"][this_key[:-len('.json')]] = value
    return obj


def _import_keys_from_s3_http(epv_list):
    logger.debug("Begin import...")
    report = {'status': 'Success', 'message': 'The import finished successfully!'}
    count_imported_EPVs = 0
    last_imported_EPV = None
    epv = []
    for epv_key in epv_list:
        for key, contents in epv_key.items():
            if len(contents.get('pkg_list_keys')) == 0 and len(contents.get('ver_list_keys')) == 0:
                report['message'] = 'Nothing to be imported! No data found on S3 to be imported!'
                continue
            obj = {
                'ecosystem': contents.get('ecosystem'),
                'package': contents.get('package'),
                'version': contents.get('version')
            }

            try:
                # Check other Version level information and add it to common object
                if len(contents.get('ver_list_keys')) > 0:
                    first_key = contents['ver_key_prefix'] + '.json'
                    first_obj = _first_key_info(first_key, "version")
                    obj.update(first_obj)
                    ver_obj = _other_key_info(contents.get('ver_list_keys'), "version")
                    if 'analyses' in obj:
                        obj.get('analyses', {}).update(ver_obj['analyses'])
                    else:
                        obj.update(ver_obj)

                # Check Package related information and add it to package object
                if len(contents.get('pkg_list_keys')) > 0:
                    pkg_obj = _other_key_info(contents.get('pkg_list_keys'), "package")
                    if 'analyses' in obj:
                        obj.get('analyses', {}).update(pkg_obj['analyses'])
                    else:
                        obj.update(pkg_obj)

                # Create Gremlin Query
                str_gremlin = GraphPopulator.create_query_string(obj)

                if str_gremlin:
                    # Fire Gremlin HTTP query now
                    logger.info("Ingestion initialized for EPV - " +
                                obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
                    epv.append(obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
                    payload = {
                        'gremlin': str_gremlin,
                        'bindings': {
                            'pkg_name': obj.get('package'),
                            'ecosystem': obj.get('ecosystem'),
                            'version': obj.get('version')
                        }
                    }
                    response = requests.post(GREMLIN_SERVER_URL_REST, json=payload, timeout=30)
                    resp = response.json()

                    if 'status' in resp and resp['status']['code'] == 200:
                        count_imported_EPVs += 1
                        last_imported_EPV = obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version')
                    elif 'Exception-Class' in resp:
                        report['message'] = "The import failed " + resp['message']
                        report['status'] = 'Failure'
                        logger.exception(report)

            except Exception as e:
                msg = "The import failed: " + str(e)
                tb = traceback.format_exc()
                logger.error("Traceback for latest failure in import call: %s" % tb)
                raise RuntimeError(msg)

    report['epv'] = epv_list
    report['count_imported_EPVs'] = count_imported_EPVs
    if count_imported_EPVs == 0 and report['status'] == 'Success':
        report['message'] = 'Nothing to be synced to Graph!'
    report['last_imported_EPV'] = last_imported_EPV

    return report


def import_epv_from_s3_http(list_epv, select_doc=None):

    try:
        s3, s3_pkg = GETS3.storage()
        # Collect relevant files from data-source and group them by package-version.
        list_keys = []
        for epv in list_epv:
            dict_keys = {}
            ver_list_keys = []
            pkg_list_keys = []
            pkg_key_prefix = ver_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/"

            if 'name' not in epv or 'ecosystem' not in epv:
                continue
            elif 'version' not in epv or epv.get('version') is None:
                epv['version'] = ''
                # Get Package level keys
                pkg_list_keys.extend(s3_pkg.retrieve_keys(epv.get('ecosystem'), epv.get('name')))

            elif 'version' in epv and epv.get('version') is not None:
                # Get EPV level keys
                ver_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/" + epv.get('version')
                ver_list_keys.extend(s3.retrieve_keys(epv.get('ecosystem'), epv.get('name'), epv.get('version')))

            if select_doc is not None and len(select_doc) > 0:
                select_ver_doc = [ver_key_prefix + '/' + x + '.json' for x in select_doc]
                select_pkg_doc = [pkg_key_prefix + x + '.json' for x in select_doc]
                ver_list_keys = list(set(ver_list_keys).intersection(set(select_ver_doc)))
                pkg_list_keys = list(set(pkg_list_keys).intersection(set(select_pkg_doc)))

            dict_keys[pkg_key_prefix] = {
                'ver_list_keys': ver_list_keys,
                'ver_key_prefix': ver_key_prefix,
                'pkg_list_keys': pkg_list_keys,
                'pkg_key_prefix': pkg_key_prefix,
                'package': epv.get('name'),
                'version': epv.get('version', ''),
                'ecosystem': epv.get('ecosystem')
            }

            list_keys.append(dict_keys)

        # Import the S3 data
        report = _import_keys_from_s3_http(list_keys)

    except Exception as e:
        msg = "The import failed: " + str(e)
        raise RuntimeError(msg)

    return report
