#!/usr/bin/env bash

DISPATCHER_YAML_FILES_DIR="/usr/lib/python3.4/site-packages/cucoslib/dispatcher"
WORKER_NAME="${WORKER_NAME:-bayesian}"

set -e
DIR=$(dirname "${BASH_SOURCE[0]}")
source $DIR/env.sh

celery --version

if [ -z "${WORKER_QUEUES}" ]; then
    WORKER_QUEUES=`selinonlib-cli inspect  \
      -n ${DISPATCHER_YAML_FILES_DIR}/nodes.yml  \
      -f ${DISPATCHER_YAML_FILES_DIR}/flows/*.yml  \
      --list-task-queues --list-dispatcher-queue | cut -d':' -f2 | sort -u | tr '\n' ','`
    WORKER_QUEUES="${WORKER_QUEUES:0:-1}"  # remove trailing ','
fi

# Keep celery worker as minimal as possible to avoid sending messages that we don't really care about
# Also keep prefetch equal to 0 as boto library hangs in an infinite loop when prefetch is set to non-zero
exec celery worker -P solo -A cucoslib.start -Q "${WORKER_QUEUES}" -l debug --concurrency=1 --prefetch-multiplier=0 -Ofair --without-gossip --without-mingle --without-heartbeat
