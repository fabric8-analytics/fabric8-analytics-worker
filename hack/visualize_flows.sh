#!/bin/bash

DISPATCHER_CONF_DIR=${DISPATCHER_CONF_DIR:-'../f8a_worker/dispatcher/'}

which selinonlib-cli 2>/dev/null >&1 || {
    echo 'Please install selinonlib-cli to visualize flow by running `pip3 install selinonlib`'
    exit 1
}

# This also performs additional checks, so if you make changes, you can be ensured that the YAML file will be
# actually correct
# As we are using custom predicates and we want to make sure that the queue
# expansion name is done correctly, export expected env vars
PYTHONPATH='../' DEPLOYMENT_PREFIX='plot_' WORKER_ADMINISTRATION_REGION="api" \
    selinonlib-cli plot --nodes-definition "${DISPATCHER_CONF_DIR}/nodes.yml" \
                        --flow-definitions "${DISPATCHER_CONF_DIR}"/flows/*.yml \
                        --format png --output-dir . && echo "Graphs are available in the current directory"


# If you want to produce Dispatcher configuration in Python, run:
#PYTHONPATH='../' DEPLOYMENT_PREFIX='dump_' WORKER_ADMINISTRATION_REGION="api" \
#    selinonlib-cli inspect --nodes-definition "${DISPATCHER_CONF_DIR}/nodes.yml" \
#                       --flow-definitions "${DISPATCHER_CONF_DIR}"/flows/*.yml \
#                       --dump out.py
