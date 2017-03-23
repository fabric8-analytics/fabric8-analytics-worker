import os
from flexmock import flexmock
import pytest
import cucoslib
from cucoslib.workers.bigquery_gh import BigQueryProject, BigQueryTask, compute_percentile_ranks


@pytest.mark.usefixtures("dispatcher_setup")
class TestBigQueryGH(object):

    json_key = os.path.join(os.path.dirname(__file__), '../data/bigquery.json')

    def test_project_id(self):
        flexmock(cucoslib.workers.bigquery_gh).should_receive('get_client').once()
        bq = BigQueryProject(json_key=TestBigQueryGH.json_key)
        assert bq.project_id == 'test-project-000001'

    def test_process_results(self):
        data = [{'name': 'underscore', 'version': '1.8.3', 'count': 101},
                {'name': 'isarray', 'version': '2.0.2', 'count': 345}]

        results = list(data)
        BigQueryTask.process_results(results)
        for result in results:
            assert sorted(result) == sorted(['name', 'version', 'count', 'ecosystem_backend'])
            assert 'percentile_rank' not in result

        results = list(data)
        BigQueryTask.process_results(results, percentile_rank=True)
        for result in results:
            assert 'percentile_rank' in result

    @pytest.mark.parametrize('test_input, expected', [
        ([1, 1, 1, 1, 1], {1: 100}),
        ([1, 2, 3, 4, 5], {1: 20, 2: 40, 3: 60, 4: 80, 5: 100}),
        ([1, 1, 1, 2, 5, 5, 11, 11, 17, 21], {1: 30, 2: 40, 5: 60, 11: 80, 17: 90, 21: 100})
    ])
    def test_compute_percentile_ranks(self, test_input, expected):
        assert compute_percentile_ranks(test_input) == expected
