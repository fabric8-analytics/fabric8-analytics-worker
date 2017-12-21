#!/bin/bash

DISPATCHER_CONF_DIR=${DISPATCHER_CONF_DIR:-'../f8a_worker/dispatcher/'}
MIGRATION_DIR=${MIGRATION_DIR:-'../f8a_worker/dispatcher/migration_dir'}

which selinonlib-cli 2>/dev/null >&1 || {
    echo "Please install selinonlib-cli to visualize flow by running 'pip3 install selinonlib'"
    exit 1
}

# As we are using custom predicates and we want to make sure that the queue
# expansion name is done correctly, export expected env vars.
PYTHONPATH='../' DEPLOYMENT_PREFIX='plot_' WORKER_ADMINISTRATION_REGION="api" \
    selinonlib-cli -vvvv migrate --nodes-definition "${DISPATCHER_CONF_DIR}/nodes.yml" \
                        --flow-definitions "${DISPATCHER_CONF_DIR}"/flows/*.yml \
			--git --migration-dir "${MIGRATION_DIR}" \
			--no-meta &&\
                        echo "Flow migration is present in the migration dir, don't forget to commit it with your flow changes."
