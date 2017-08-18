class TestSentimentScorer(object):
    def test_import(self):
        # https://github.com/fabric8-analytics/fabric8-analytics-worker/issues/261
        from google.cloud import language
        from google.cloud import bigquery
