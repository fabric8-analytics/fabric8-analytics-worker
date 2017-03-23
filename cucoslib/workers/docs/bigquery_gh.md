BigQuery_GH worker
------------------

This worker can crawl through all `package.json` files located in top-level directories in all public GitHub repositories and extract a list of dependencies from them. It does so by querying BigQuery's public GitHub dataset (`[bigquery-public-data:github_repos]`). Since BigQuery charges for querying data, the worker stores all results in our PostgreSQL database.

Note this worker requires a JSON key for access to the BigQuery service, see the [configuration section](#configuration) for details.

Known limitations:
- only NPM is supported
- worker treats forked repositories equally to original ones
- worker ignores version of dependencies


#### Configuration

This worker is meant to be run periodically and the interval is configurable, see [cucoslib.celery_settings.CELERYBEAT_SCHEDULE](../../celery_settings.py) for the default settings.

By default, the worker looks for the JSON key required for communication with the BigQuery service in `/var/lib/secrets/bigquery.json`. You can either put your key there, or you can override the location via `BIGQUERY_JSON_KEY` environment variable.
You can generate the key in the [Google API Console](https://console.developers.google.com/) (authentication required).