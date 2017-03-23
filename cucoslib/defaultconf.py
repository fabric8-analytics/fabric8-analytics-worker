data = {
    "postgres": {
        # TODO: find out if this uses SSL by default and if not, enable it
        "connection_string": "postgres://coreapi:coreapi@localhost:5432/coreapi"
    },
    "cve_db_mongo": {
        "connection_string": "mongodb://localhost:27017"
    },
    "coreapi_server": {
        "url": "http://coreapi-server:32000",
    },
    # URL to npmjs couch DB, which returns stream of changes happening in npm registry
    "npmjs_changes_url": "https://skimdb.npmjs.com/registry/_changes?descending=true&include_docs=true&feed=continuous",
    "git": {
        "user_name": "cucos",             # git config user.name
        "user_email": "cucos@cucos.ccs"   # git config user.email
    },
    "broker": {
        "connection_string": "amqp://localhost:5672"
    },
    "anitya": {
        "url": "http://localhost:31005"
    },
    "bigquery": {
        "json_key": "/var/lib/secrets/bigquery.json"
    },
}
