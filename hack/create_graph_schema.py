import os
import requests
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


GREMLIN_SERVER_URL_REST = "http://{host}:{port}".format(
                          host=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_HOST", "localhost"),
                          port=os.environ.get("BAYESIAN_GREMLIN_HTTP_SERVICE_PORT", "8182"))

GRAPH_INITIALIZED = False
SCHEMA_CREATED = False
# wait for graph to be initialized
while not GRAPH_INITIALIZED:
    try:
        logger.debug("Calling GREMLIN - " + GREMLIN_SERVER_URL_REST)
        resp = requests.get(GREMLIN_SERVER_URL_REST)
        if resp.status_code >= 200:
            logger.debug("Gremlin Instance available")
            GRAPH_INITIALIZED = True
            break
    except:
        logger.debug("Waiting for Gremlin HTTP to be initialized. Sleeping for 10 seconds")
        time.sleep(10)
        continue

# send the schema payload for creation
current_file_path = os.path.dirname(os.path.realpath(__file__))
schema_file_path = os.path.join(current_file_path, 'schema.groovy')
with open(schema_file_path, 'r') as f:
    str_gremlin_dsl = f.read()

while not SCHEMA_CREATED:
    logger.debug("Creating Graph Schema Now...")
    payload = {'gremlin': str_gremlin_dsl}

    response = requests.post(GREMLIN_SERVER_URL_REST, json=payload)

    if response.status_code != 200:
        msg = "ERROR Creating Schema - %d(%s): %s" % (response.status_code, response.reason,
                                                      response.json().get("message"))
        raise RuntimeError(msg)
    else:
        SCHEMA_CREATED = True
