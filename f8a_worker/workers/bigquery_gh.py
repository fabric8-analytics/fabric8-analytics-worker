"""Worker for querying GitHub package/component usage data from BigQuery."""

import os
import collections
import csv
import json
import tempfile
import psycopg2
from selinon import SelinonTask
from celery.utils.log import get_task_logger
from bigquery import get_client, JOB_WRITE_TRUNCATE, JOB_WRITE_EMPTY
from bigquery.errors import BigQueryTimeoutException
from selinon import StoragePool

from f8a_worker.defaults import configuration
from f8a_worker.storages import AmazonS3

logger = get_task_logger(__name__)

# get all dependencies from all package.json files on GitHub and count their occurrences
query_dependents_count = """
SELECT
  REGEXP_EXTRACT(name_version, r'^\"([a-zA-Z0-9-@]{{1}}[a-zA-Z0-9-._/]+)\"') AS name,
  COUNT(name) AS count
FROM (
  SELECT
    SPLIT(RTRIM(LTRIM(JSON_EXTRACT(content, '$.dependencies'), '{{' ), '}}' ), ',') AS name_version
  FROM
    [{project_id}:{dataset}.github_package_jsons])
GROUP BY
  name
HAVING
  count > 0
"""


shrinkwrap_refs = """
SELECT
  name,
  version,
  COUNT(name) AS count
FROM
  # UDF, see resources/bigquery_gh/udfs.js
  extractDependencies(
  SELECT
    content
  FROM
    [{project_id}:{dataset}.github_shrinkwrap_jsons])
GROUP BY
  name,
  version
HAVING
  count > 0
"""


# get contents of all top-level package.json files
# TODO: figure out how exclude forked repositories
files_contents = """
SELECT
  CONTENTS.content as content
FROM
  [bigquery-public-data:github_repos.contents] AS CONTENTS
JOIN (
  SELECT
    id
  FROM
    [bigquery-public-data:github_repos.files]
  WHERE
    path = '{filename}'
  GROUP BY
    id) AS FIELDS
ON
  CONTENTS.id = FIELDS.id
"""

_DEFAULT_BUCKET_NAME = 'bayesian-core-bigquery-data'


class BigQueryTask(SelinonTask):
    def run(self, node_args):
        """Get package usage information from BigQuery's public GitHub dataset."""
        dataset = 'bayesian'
        json_key = configuration.BIGQUERY_JSON_KEY
        try:
            bq = BigQueryProject(json_key=json_key)
        except ValueError as e:
            logger.error(str(e))
            return

        # find all package.json files and store them into a separate table
        bq.execute_query(query_str=files_contents.format(filename='package.json'),
                         dest_dataset=dataset,
                         dest_table='github_package_jsons',
                         allow_large_results=True,
                         write_disposition=JOB_WRITE_TRUNCATE)

        results = bq.execute_query(query_dependents_count.format(project_id=bq.project_id,
                                                                 dataset=dataset))
        if results:
            self.store_results(results, 'package_gh_usage')
        else:
            logger.info('No results from BigQuery')

        # find all npm-shrinkwrap.json files and store them into a separate table
        bq.execute_query(query_str=files_contents.format(filename='npm-shrinkwrap.json'),
                         dest_dataset=dataset,
                         dest_table='github_shrinkwrap_jsons',
                         allow_large_results=True,
                         write_disposition=JOB_WRITE_TRUNCATE)

        # TODO: figure out how to automatically upload the file containing UDFs
        # to the Google Cloud Storage
        # TODO: make the bucket name configurable
        results = bq.execute_query(query_str=shrinkwrap_refs.format(project_id=bq.project_id,
                                                                    dataset=dataset),
                                   udf_uris=["gs://{project_id}.appspot.com/udfs.js".format(
                                       project_id=bq.project_id)])
        if results:
            self.process_results(results, percentile_rank=True)
            self.store_results(results, 'component_gh_usage')
        else:
            logger.info('No results from BigQuery')

    @classmethod
    def store_results(cls, results, table_name):
        """Store results from BigQuery in our DB."""
        # TODO: implement store() method in S3BigQuery for this and assign
        # S3BigQuery to this task in nodes.yml
        csv_file = None
        try:
            csv_file, csv_header = cls.prepare_csv_file(results)
            cls.dump_to_rdb(csv_file, csv_header, table_name)

            if AmazonS3.is_enabled():
                s3 = StoragePool.get_connected_storage('S3BigQuery')
                s3.store_file(csv_file, table_name)

        finally:
            if csv_file:
                os.unlink(csv_file)

    @staticmethod
    def prepare_csv_file(results):
        """Dump BigQuery results to a CSV file."""
        csv_header = results[0].keys()
        fd, csv_file = tempfile.mkstemp(prefix='bigquery_result', text=True)
        with os.fdopen(fd, 'w') as f:
            dict_writer = csv.DictWriter(f, results[0].keys())
            dict_writer.writerows(results)
        return csv_file, csv_header

    @staticmethod
    def process_results(bq_results, percentile_rank=False):
        if percentile_rank:
            counts = [x['count'] for x in bq_results]
            counts.sort()
            ranks = compute_percentile_ranks(counts)
        for res in bq_results:
            # TODO: only NPM is supported now
            res['ecosystem_backend'] = 'npm'
            if percentile_rank:
                res['percentile_rank'] = ranks[res['count']]

    @staticmethod
    def dump_to_rdb(csv_file, csv_header, table_name):
        """Import results from BigQuery into the DB."""
        conn = psycopg2.connect(configuration.POSTGRES_CONNECTION)
        try:
            cur = conn.cursor()
            cur.copy_from(open(csv_file), table_name, sep=',', columns=csv_header)
            conn.commit()
        except Exception:
            raise
        finally:
            conn.close()


class BigQueryProject(object):

    def __init__(self, json_key):
        """Initialize the object.

        :param json_key: path to the JSON key containing BigQuery credentials
        """
        if not os.path.isfile(json_key):
            raise ValueError('BigQuery JSON key is missing, cannot continue... (path={f})'.format(
                f=json_key))
        self._json_key = json_key
        self._client = get_client(json_key_file=self._json_key, readonly=False)
        self.project_id = self._extract_project_id()

    def execute_query(self, query_str, dest_dataset=None, dest_table=None,
                      allow_large_results=False, write_disposition=JOB_WRITE_EMPTY, timeout=300,
                      udf_uris=None):
        """Execute query in BigQuery.

        :param query_str: query string to execute
        :param dest_dataset: name of the dataset
        :param dest_table: name of the destination table
        :param allow_large_results: if True, allows arbitrarily large results
               to be written to the destination table
        :param write_disposition: specifies the action that occurs if the
               destination table already exists, see `bigquery.JOB_WRITE_*` constants.
        :param timeout: time (in seconds) how long to wait for a job to finish
               before raising bigquery.errors.BigQueryTimeoutException
        :param udf_uris: list of resources to load from a Google Cloud Storage
               URI (e.g.: ['gs://bucket/path']).
        :return: response from BigQuery
        """
        permanent_table = False
        if dest_dataset and dest_table:
            self._create_dataset(dest_dataset)
            permanent_table = True
        try:
            if permanent_table or udf_uris:
                # store results in a table
                if udf_uris is None:
                    udf_uris = []
                job = self._client.write_to_table(
                    query_str,
                    dataset=dest_dataset,
                    table=dest_table,
                    allow_large_results=allow_large_results,
                    write_disposition=write_disposition,
                    external_udf_uris=udf_uris
                )

                job_resource = self._client.wait_for_job(job, timeout=timeout)
                logger.debug('BigQuery job has finished: {r}'.format(r=job_resource))
                if not permanent_table:
                    # python-BigQuery library only supports UDFs in combination
                    # with storing results to a temporary/permanent table. If
                    # it's just a temporary table, we want to return actual
                    # results.
                    results = self._client.get_query_rows(job['jobReference']['jobId'])
                    return results
                return job_resource
            else:
                _, results = self._client.query(query_str, timeout=timeout)
                logger.debug("BigQuery has returned {n} results.".format(n=len(results)))
                return results
        except BigQueryTimeoutException:
            logger.error("BigQuery job hasn't finished in {t} seconds.".format(t=timeout),
                         exc_info=True)
            raise

    def _create_dataset(self, dataset_name):
        """Create dataset, if it doesn't exist yet.

        :param dataset_name: name of the dataset
        """
        dataset_exists = self._client.check_dataset(dataset_name)
        if not dataset_exists:
            logger.info("Creating '{ds}' dataset.".format(ds=dataset_name))
            self._client.create_dataset(dataset_name)
        else:
            logger.debug("'{ds}' dataset already exists.".format(ds=dataset_name))

    def _extract_project_id(self):
        with open(self._json_key, 'r') as f:
            key = json.load(f)
            return key['project_id']


def compute_percentile_ranks(sorted_list):
    """Compute percentile ranks for all elements in the `sorted_list`.

    :param sorted_list: sorted list of elements
    :return: dict containing element->percentile rank mapping

    >>> compute_percentile_ranks([1, 1, 1, 1, 1])
    OrderedDict([(1, 100)])
    >>> compute_percentile_ranks([1, 2, 3, 4, 5])
    OrderedDict([(1, 20), (2, 40), (3, 60), (4, 80), (5, 100)])
    >>> compute_percentile_ranks(['E', 'E', 'E', 'D', 'D', 'D', 'C', 'B', 'A', 'A'])
    OrderedDict([('E', 30), ('D', 60), ('C', 70), ('B', 80), ('A', 100)])
    """
    # get frequency of elements in the input array
    freq = collections.OrderedDict()
    for elem in sorted_list:
        freq[elem] = freq.get(elem, 0) + 1

    # compute the percentile ranks
    percentile_ranks = collections.OrderedDict()
    percentile = 0.0
    for (elem, count) in freq.items():
        percentile += count / len(sorted_list)
        percentile_ranks[elem] = round(percentile * 100)

    return percentile_ranks
