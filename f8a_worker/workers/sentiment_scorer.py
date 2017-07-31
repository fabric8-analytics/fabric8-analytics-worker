"""
Gathers component data from the graph database and aggregate the data to be presented
by stack-analyses endpoint

Output: TBD

"""

import os
import json
import requests
import abc
import os
import datetime
# import asyncio
import time

import requests
import json
import logging

from f8a_worker.base import BaseTask
from f8a_worker.graphutils import GREMLIN_SERVER_URL_REST
from f8a_worker.utils import get_session_retry


from joblib import Parallel, delayed

from google.cloud import language
from google.cloud import bigquery

logger = logging.getLogger(__name__)

class SentimentAnalyzer(object):
    @abc.abstractmethod
    def analyze_sentiment(self, text):
        return


class GoogleSentimentAnalyzer(SentimentAnalyzer):
    def __init__(self, key_file_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_file_path
        self.lang_client = language.Client()

    def analyze_sentiment(self, text):
        start_time = time.time()

        document = self.lang_client.document_from_text(text)
        annotations = document.annotate_text(include_sentiment=True,
                                             include_syntax=False,
                                             include_entities=False)
        score = annotations.sentiment.score
        magnitude = annotations.sentiment.magnitude
        logger.info('Sentiment score and magnitude is computed successfully.')
        return score, magnitude


class ExternalDataStore(object):
    @abc.abstractmethod
    def get_stack_overflow_data(self, search_keyword, search_tag, num_months):
        return


class GooglePublicDataStore(ExternalDataStore):
    def __init__(self, key_file_path):
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = key_file_path
        self.big_query_client = bigquery.Client()

    def __run_query(self, sql):
        query = self.big_query_client.run_sync_query(sql)
        query.timeout_ms = 60000
        query.use_legacy_sql = False
        query.use_query_cache = True
        query.run()
        aggregated_text = ''
        for row in query.rows:
            aggregated_text = aggregated_text + row[0] + ' '

        return aggregated_text

    def get_stack_overflow_data(self, search_keyword, search_tag, num_months, max_len=90000):
        start_time = time.time()
        logger.info('Started to collect data from stackoverflow for package: {}'.format(search_keyword))
        min_date = datetime.date.today() - datetime.timedelta(num_months*365/12)
        min_timestamp = min_date.strftime("%Y-%m-%d %H:%M:%S")
        sql_for_questions = \
            """
            SELECT   body, creation_date, tags
            FROM     {table_name}
            WHERE    body like '%{search_keyword}%' 
            AND      tags like '%{search_tag}%'
            AND      creation_date >= '{min_timestamp}'
            """.format(table_name="`bigquery-public-data.stackoverflow.posts_questions`",
                       search_keyword=search_keyword,
                       search_tag=search_tag,
                       min_timestamp=min_timestamp)
        questions = self.__run_query(sql_for_questions)

        sql_for_answers = \
            """
            SELECT   body, creation_date, tags
            FROM     {table_name}
            WHERE    body like '%{search_keyword}%' 
            AND      creation_date >= '{min_timestamp}'
            """.format(table_name="`bigquery-public-data.stackoverflow.posts_answers`",
                       search_keyword=search_keyword,
                       min_timestamp=min_timestamp)
        answers = self.__run_query(sql_for_answers)

        # loop = asyncio.get_event_loop()
        # futures = [self.__run_query(i) for i in [sql_for_questions, sql_for_answers]]
        # group_future = asyncio.gather(*futures)
        # output = loop.run_until_complete(group_future)

        # output_data = output[0] + output[1]
        output_data = questions + answers
        logger.info('Successfully collected data from stackoverflow for package: {}'.format(search_keyword))
        return output_data[:max_len] if len(output_data) > max_len else output_data


class SentimentCache(object):
    @abc.abstractmethod
    def get_sentiment_details(self, key_name):
        return

    @abc.abstractmethod
    def set_sentiment_details(self, key_name, key_value):
        return


class SentimentGraphStore(SentimentCache):
    def __init__(self, graph_db_url):
        self.graph_db_url = graph_db_url

    def __execute_query(self, query):
        """
        :param query:
        :return: query response
        """
        payload = {'gremlin': query}
        response = get_session_retry().post(self.graph_db_url, data=json.dumps(payload))

        if response.status_code == 200:
            return response.json()
        else:
            logger.info('Graph is not giving response.')
            return {}

    def get_sentiment_details(self, key_name):
        query = "g.V().has('name','" + key_name + "').toList()"
        pkg_data = self.__execute_query(query)
        pkg_properties = None
        if 'result' in pkg_data:
            raw_pkgdata = pkg_data.get('result').get('data', [])
            if raw_pkgdata:
                pkg_properties = raw_pkgdata[0].get('properties', [])

        sentiment_details = {}
        if pkg_properties:
            sentiment_details['package_name'] = key_name
            sentiment_details['score'] = \
                float(pkg_properties.get('sentiment_score')[0].get('value', 0)) \
                if 'sentiment_score' in pkg_properties else None
            sentiment_details['magnitude'] = \
                float(pkg_properties.get('sentiment_magnitude')[0].get('value', 0)) \
                if 'sentiment_magnitude' in pkg_properties else None
            sentiment_details['last_updated'] = \
                pkg_properties.get('last_updated_sentiment_score')[0].get('value', 0) \
                if 'last_updated_sentiment_score' in pkg_properties else None
        return sentiment_details

    def set_sentiment_details(self, key_name, key_value):
        pkg_name = key_name
        sentiment_details = key_value

        query = \
            """
            g.V().has('name', '{pkg_name}').
            property('sentiment_score', '{score}').
            property('sentiment_magnitude', '{magnitude}').
            property('last_updated_sentiment_score', '{last_updated}').
            toList();
            """.format(pkg_name=pkg_name,
                       score=sentiment_details['score'],
                       magnitude=sentiment_details['magnitude'],
                       last_updated=sentiment_details['last_updated'])
        self.__execute_query(query)
        return


def write_key_file(local_path):
    type = os.getenv("GCP_TYPE", "")
    project_id = os.getenv("GCP_PROJECT_ID", "")
    private_key_id = os.getenv("GCP_PRIVATE_KEY_ID", "")
    private_key = os.getenv("GCP_PRIVATE_KEY", "")
    client_email = os.getenv("GCP_CLIENT_EMAIL", "")
    client_id = os.getenv("GCP_CLIENT_ID", "")
    auth_uri = os.getenv("GCP_AUTH_URI", "")
    token_uri = os.getenv("GCP_TOKEN_URI", "")
    auth_provider_cert_url = os.getenv("GCP_AUTH_PROVIDER_X509_CERT_URL", "")
    client_url = os.getenv("GCP_CLIENT_X509_CERT_URL", "")

    key_file_contents = \
        """
        {{
          "type": "{type}",
          "project_id": "{project_id}",
          "private_key_id": "{private_key_id}",
          "private_key": "{private_key}",
          "client_email": "{client_email}",
          "client_id": "{client_id}",
          "auth_uri": "{auth_uri}",
          "token_uri": "{token_uri}",
          "auth_provider_x509_cert_url": "{auth_provider_cert_url}",
          "client_x509_cert_url": "{client_url}"
        }}
        """.format(type=type,
                   project_id=project_id,
                   private_key_id=private_key_id,
                   private_key=private_key,
                   client_email=client_email,
                   client_id=client_id,
                   auth_uri=auth_uri,
                   token_uri=token_uri,
                   auth_provider_cert_url=auth_provider_cert_url,
                   client_url=client_url)

    key_file = open(local_path, "w")
    key_file.write(key_file_contents)
    key_file.close()


def sentiment_analysis(arg):
    key_file = "/tmp/key.json"
    write_key_file(local_path=key_file)
    ecosystem, pkg_name = arg

    logger.info('Starting the sentiment analysis for package: {}'.format(pkg_name))
    # First, check if package sentiment is available in cache i.e. graph db
    sentiment_cache = SentimentGraphStore(graph_db_url=GREMLIN_SERVER_URL_REST)
    sentiment_output = sentiment_cache.get_sentiment_details(key_name=pkg_name)
    if len(sentiment_output.items()) == 0:  # package not found in graph i.e. unknown
        return {}

    # Let us now check if package sentiment is fresh enough or not
    flag_refresh = True
    today_date = datetime.datetime.today()
    if sentiment_output['last_updated']:
        last_updated = datetime.datetime.strptime(sentiment_output['last_updated'],
                                                  "%Y-%m-%d")
        time_diff = today_date - last_updated
        if time_diff.days <= 7:  # Found data in cache
            flag_refresh = False

    # Compute fresh package-sentiment if required
    if flag_refresh:
        # TODO decide stack-overflow tag for other ecosystems
        search_tag = 'python' if ecosystem == 'pypi' else ecosystem
        data_store = GooglePublicDataStore(key_file_path=key_file)
        text = data_store.get_stack_overflow_data(search_keyword=pkg_name,
                                                  search_tag=search_tag,
                                                  num_months=6)

        sentiment_analyzer = GoogleSentimentAnalyzer(key_file_path=key_file)
        score, magnitude = sentiment_analyzer.analyze_sentiment(text=text)

        sentiment_output = {
            'package_name': pkg_name,
            'score': score,
            'magnitude': magnitude,
            'last_updated': today_date.strftime("%Y-%m-%d")
        }

        sentiment_cache.set_sentiment_details(key_name=pkg_name,
                                              key_value=sentiment_output)

    return sentiment_output


class UserStackSentimentScoringTask(BaseTask):
    description = 'Sentiment scoring for the packages in user-stack'
    _analysis_name = 'user_stack_sentiment_scorer'

    def execute(self, arguments=None):
        aggregated = self.parent_task_result('GraphAggregatorTask')

        sentiment_output = {}
        arg_instances = []
        for result in aggregated['result']:
            resolved = result['details'][0]['_resolved']
            ecosystem = result['details'][0]['ecosystem']
            for elm in resolved:
                arg_instances.append((ecosystem, elm['package']))

        sentiment_results = Parallel(n_jobs=4, verbose=1, backend="threading")\
            (map(delayed(sentiment_analysis), arg_instances))
        for r in sentiment_results:
            sentiment_output[r['package_name']] = r

        return sentiment_output


class RecoPkgSentimentScoringTask(BaseTask):
    description = 'Sentiment scoring for the recommended packages'
    _analysis_name = 'reco_pkg_sentiment_scorer'

    def execute(self, arguments=None):
        parent_result = self.parent_task_result('recommendation_v2')

        sentiment_output = {}
        arg_instances = []
        recommendations = parent_result['recommendations']
        for pkg in recommendations['alternate']:
            arg_instances.append((pkg['ecosystem'], pkg['name']))
        for pkg in recommendations['companion']:
            arg_instances.append((pkg['ecosystem'], pkg['name']))

        sentiment_results = Parallel(n_jobs=4, verbose=1, backend="threading")\
            (map(delayed(sentiment_analysis), arg_instances))
        for r in sentiment_results:
            sentiment_output[r['package_name']] = r

        return sentiment_output
