import os
import requests
import logging
import json
import traceback
import botocore
import boto3
import time
from datetime import datetime
from f8a_worker.workers.graph_populator import GraphPopulator
# from botocore.exceptions import

logger = logging.getLogger(__name__)

# Get Variable Parameters from Environment
GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format(
                           host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost"),
                           port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182"))
AWS_EPV_BUCKET = os.environ.get("AWS_EPV_BUCKET", "")
AWS_PKG_BUCKET = os.environ.get("AWS_PKG_BUCKET", "")
LOCAL_MINIO_ENDPOINT = os.environ.get("LOCAL_MINIO_ENDPOINT", "coreapi-s3:33000")
access_key = os.environ.get("AWS_S3_ACCESS_KEY_ID")
secret_key = os.environ.get("AWS_S3_SECRET_ACCESS_KEY")
s3_resource = None

if os.environ.get("AWS_S3_IS_LOCAL") and int(os.environ.get("AWS_S3_IS_LOCAL")) == 1:
    global s3_resource
    # access_key = os.environ.get("MINIO_ACCESS_KEY")
    # secret_key = os.environ.get("MINIO_SECRET_KEY")
    session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                                    region_name="us-east-1")
    s3_resource = session.resource('s3', config=botocore.client.Config(signature_version='s3v4'),
                                   use_ssl=False, endpoint_url="http://" + LOCAL_MINIO_ENDPOINT)
else:
    global s3_resource
    # access_key = os.environ.get("AWS_S3_ACCESS_KEY_ID")
    # secret_key = os.environ.get("AWS_S3_SECRET_ACCESS_KEY")
    session = boto3.session.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
    s3_resource = session.resource('s3', config=botocore.client.Config(signature_version='s3v4'))


def read_json_file(filename, bucket_name=None):
    """Read JSON file from the data source"""

    global s3_resource
    if bucket_name is None:
        bucket_name = AWS_EPV_BUCKET

    obj = s3_resource.Object(bucket_name, filename).get()['Body'].read()
    utf_data = obj.decode("utf-8")
    return json.loads(utf_data)


def list_files(prefix=None, bucket_name=None):
    """List all the files in the source directory"""

    global s3_resource
    if bucket_name is None:
        bucket_name = AWS_EPV_BUCKET

    bucket = s3_resource.Bucket(bucket_name)

    if prefix is None:
        objects = bucket.objects.all()
    else:
        objects = bucket.objects.filter(Prefix=prefix)

    list_filenames = [x.key for x in objects if x.key.endswith('.json')]

    return list_filenames


def _first_key_info(first_key, bucket_name=None):
    obj = {}
    t = read_json_file(first_key, bucket_name)
    obj["dependents_count"] = t.get("dependents_count", '-1')
    obj["package_info"] = t.get("package_info", {})
    obj["latest_version"] = t.get("latest_version", '-1')
    return obj


def _other_key_info(other_keys, bucket_name=None):
    obj = {"analyses": {}}
    for this_key in other_keys:
        value = read_json_file(this_key, bucket_name)
        this_key = this_key.split("/")[-1]
        if 'success' == value.get('status', ''):
            obj["analyses"][this_key[:-len('.json')]] = value
    return obj


def _get_exception_msg(prefix, e):
    msg = prefix + ": " + str(e)
    logger.error(msg)
    tb = traceback.format_exc()
    logger.error("Traceback for latest failure in import call: %s" % tb)
    return msg


def _log_report_msg(import_type, report):
    # Log the report
    msg = """
        Report from {}:
        {}
        Total number of EPVs imported: {}
        The last successfully imported EPV: {}
    """
    msg = msg.format(import_type, report.get('message'),
                     report.get('count_imported_EPVs'),
                     report.get('last_imported_EPV'))

    if report.get('status') is 'Success':
        logger.debug(msg)
    else:
        # TODO: retry??
        logger.error(msg)


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
                    first_obj = _first_key_info(first_key, AWS_EPV_BUCKET)
                    obj.update(first_obj)
                    ver_obj = _other_key_info(contents.get('ver_list_keys'), AWS_EPV_BUCKET)
                    if 'analyses' in obj:
                        obj.get('analyses', {}).update(ver_obj['analyses'])
                    else:
                        obj.update(ver_obj)

                # Check Package related information and add it to package object
                if len(contents.get('pkg_list_keys')) > 0:
                    pkg_obj = _other_key_info(contents.get('pkg_list_keys'), AWS_PKG_BUCKET)
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
                    payload = {'gremlin': str_gremlin}
                    response = requests.post(GREMLIN_SERVER_URL_REST, data=json.dumps(payload), timeout=30)
                    resp = response.json()

                    if 'status' in resp and resp['status']['code'] == 200:
                        count_imported_EPVs += 1
                        last_imported_EPV = obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version')
                    elif 'Exception-Class' in resp:
                        report['message'] = "The import failed " + resp['Exception-Class']

            except Exception as e:
                msg = _get_exception_msg("The import failed", e)
                report['status'] = 'Failure'
                report['message'] = msg
                report['epv'] = epv_key

    report['epv'] = epv_list
    report['count_imported_EPVs'] = count_imported_EPVs
    if count_imported_EPVs == 0 and report['status'] == 'Success':
        report['message'] = 'Nothing to be synced to Graph!'
    report['last_imported_EPV'] = last_imported_EPV

    return report


def import_epv_from_s3_http(list_epv, select_doc=None):
    try:
        # Collect relevant files from data-source and group them by package-version.
        list_keys = []
        for epv in list_epv:
            dict_keys = {}
            ver_list_keys = []
            pkg_list_keys = []

            if 'name' not in epv or 'ecosystem' not in epv:
                continue
            else:
                # Get Package level keys
                pkg_key_prefix = ver_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/"
                pkg_list_keys.extend(list_files(bucket_name=AWS_PKG_BUCKET, prefix=pkg_key_prefix))

            if 'version' in epv and epv.get('version') is not None:
                # Get EPV level keys
                ver_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/" + epv.get('version')
                ver_list_keys.extend(list_files(bucket_name=AWS_EPV_BUCKET, prefix=ver_key_prefix + "/"))
            else:
                epv['version'] = ''
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

        # Log the report
        _log_report_msg("import_epv()", report)

    except Exception as e:
        msg = _get_exception_msg("import_epv() failed with error", e)
        raise RuntimeError(msg)
    return report

