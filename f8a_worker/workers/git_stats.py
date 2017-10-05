import numpy as np
from time import time
from datetime import timedelta
from sklearn.linear_model import LinearRegression

from f8a_worker.process import Git
from f8a_worker.base import BaseTask
from f8a_worker.utils import tempdir


class GitStats(BaseTask):
    """Collect and compute Git statistics."""

    _SECONDS_PER_DAY = 60 * 60 * 24
    _DAYS_PER_MONTH = 30
    _DAYS_PER_YEAR = 365
    _TREND_TRESHOLD = 0.3

    @staticmethod
    def _get_log(url):
        """Clone Git repo and get its log.

        :param url: url to the git repo
        """
        with tempdir() as tmp_dir:
            git = Git.clone(url, tmp_dir)
            # nice notebook to check at:
            #   http://nbviewer.jupyter.org/github/tarmstrong/code-analysis/blob/master/IPythonReviewTime.ipynb
            log = git.log()

        return log

    @staticmethod
    def _get_average_changes(log):
        """Compute average changes based on log.

        :param log: log on which changes should be computed
        :return: a tuple containing aggregated changes across the whole log
        """
        additions = 0
        deletions = 0
        count = 0
        for entry in log:
            for change in entry['changes']:
                if isinstance(change[0], int):
                    additions += change[0]
                if isinstance(change[1], int):
                    deletions += change[1]
                count += 1

        if count:
            additions /= count
            deletions /= count

        return additions, deletions

    @classmethod
    def _get_trend(cls, log, starting_date):
        """Get commit count trend based on log.

        :param log: a log on which the trend should be computed
        :param starting_date: starting date of log
        :return: computed trend
        """
        records = [0]
        date = starting_date
        for entry in log:
            if entry['author']['date'] > date + cls._SECONDS_PER_DAY:
                date += cls._SECONDS_PER_DAY
                records.append(0)
            records[-1] += 1

        lr = LinearRegression()
        lr.fit(np.array(range(len(records))).reshape(-1, 1), np.array(records))

        return lr.coef_[0]

    @classmethod
    def _get_trend_str(cls, trend):
        """Convert numerical representation of trend to its string representation.

        :param trend: numerical representation of thrend
        :return: textual representation of trend
        """
        if trend > cls._TREND_TRESHOLD:
            return 'increasing'
        elif trend < -cls._TREND_TRESHOLD:
            return 'decreasing'
        else:
            return 'calm'

    @staticmethod
    def _get_orgs(log):
        """Aggregate all organizations that were found in the log.

        :param log: log on which organizations should be found
        :return: a list of found organizations in the log
        """
        orgs = set()

        for entry in log:
            email = entry['author']['email'].split('@')
            if len(email) == 2:
                orgs.add(email[1])

        return list(orgs)

    @classmethod
    def _compute_stats(cls, log, starting_date):
        """Compute statisics on log.

        :param log: log entries on which statistics should be computed
        :param starting_date: starting date of log
        :return: computed statistics
        """
        trend = cls._get_trend(log, starting_date) if log else None
        return {
            'commit_count': len(log),
            'committer_count': len(list(set(item['author']['email'] for item in log))),
            'oldest_commit': log[-1]['author']['date'] if log else None,
            'newest_commit': log[0]['author']['date'] if log else None,
            'average_changes': cls._get_average_changes(log) if log else None,
            'trend': trend,
            'trend_status': cls._get_trend_str(trend) if trend else None
        }

    def execute(self, arguments):
        self._strict_assert('ecosystem' in arguments)
        self._strict_assert('name' in arguments)
        self._strict_assert('url' in arguments)

        master_log = self._get_log(arguments['url'])
        if not master_log:
            raise ValueError("No log for master branch to inspect")

        now = time()
        last_year_timestamp = now - timedelta(days=self._DAYS_PER_YEAR).total_seconds()
        last_month_timestamp = now - timedelta(days=self._DAYS_PER_MONTH).total_seconds()

        last_year_log = [item for item in master_log
                         if item['author']['date'] >= last_year_timestamp]

        last_month_log = [item for item in master_log
                          if item['author']['date'] >= last_month_timestamp]

        master_stats = {}
        records = (
            ('overall', master_log, master_log[-1]['author']['date'] if master_log else None),
            ('year', last_year_log, last_year_timestamp),
            ('month', last_month_log, last_month_timestamp)
        )
        for key, log, starting_date in records:
            master_stats[key] = self._compute_stats(log, starting_date)

        master_stats['organizations'] = self._get_orgs(master_log)

        return {'summary': [], 'status': 'success', 'details': {'master': master_stats}}
