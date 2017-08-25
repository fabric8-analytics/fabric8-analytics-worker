#!/usr/bin/env bash
# Worker startup script
# Parameters present in env variables:
#   WORKER_INCLUDE_QUEUES - a comma separated names of queues on which worker should listen on
#   WORKER_EXCLUDE_QUEUES - a comma separated names of queues on which worker should NOT listen on
#   WORKER_ADMINISTRATION_REGION - (required) worker namespace to operate on
#
# Note:
#   * WORKER_INCLUDE_QUEUES is disjoint with WORKER_EXCLUDE_QUEUES and vice versa
#   * if WORKER_EXCLUDE_QUEUES and WORKER_INCLUDE_QUEUES are not present worker will listen on all queues
#   * WORKER_EXCLUDE_QUEUES excludes queues based on list of all queues that are present according to YAML conf files

set -ex

DISPATCHER_YAML_FILES_DIR="/usr/lib/python3.4/site-packages/f8a_worker/dispatcher"
WORKER_NAME="${WORKER_NAME:-bayesian}"

DIR=$(dirname "${BASH_SOURCE[0]}")
source $DIR/env.sh

# Report versions of all core components
selinonlib-cli version

if [ -n "${WORKER_INCLUDE_QUEUES}" -a -n "${WORKER_EXCLUDE_QUEUES}" ]; then
    echo "Specify only one queue configuration - either WORKER_INCLUDE_QUEUES or WORKER_EXCLUDE_QUEUES" 1>&2
    exit 1
fi

if [ -z "${WORKER_ADMINISTRATION_REGION}" ]; then
    echo "Specify WORKER_ADMINISTRATION_REGION to distinguish worker namespace" 1>&2
    exit 1
fi

# node:queue
WORKER_QUEUES=`selinonlib-cli inspect  \
  -n ${DISPATCHER_YAML_FILES_DIR}/nodes.yml  \
  -f ${DISPATCHER_YAML_FILES_DIR}/flows/*.yml  \
  --list-task-queues --list-dispatcher-queues`

if [ -n "${WORKER_INCLUDE_QUEUES}" ]; then
    WORKER_INCLUDE_QUEUES=`echo "${WORKER_INCLUDE_QUEUES}" | tr ',' '|'`
    WORKER_QUEUES=`echo "${WORKER_QUEUES}" | egrep "${WORKER_INCLUDE_QUEUES}"`
elif [ -n "${WORKER_EXCLUDE_QUEUES}" ]; then
    WORKER_EXCLUDE_QUEUES=`echo "${WORKER_EXCLUDE_QUEUES}" | tr ',' '|'`
    WORKER_QUEUES=`echo "${WORKER_QUEUES}" | egrep -v "${WORKER_EXCLUDE_QUEUES}"`
fi

# Listen only on queues that are supposed to be served based on administration region
WORKER_QUEUES=`echo "${WORKER_QUEUES}" | grep "_${WORKER_ADMINISTRATION_REGION}_"`

# Always exclude livenessFlow queue and prepare for celery worker
WORKER_QUEUES=`echo "${WORKER_QUEUES}" | grep -v '^livenessFlow:' | cut -d':' -f2 | sort -u | tr '\n' ','`
WORKER_QUEUES="${WORKER_QUEUES:0:-1}"  # remove trailing ','

celery-prometheus-exporter &

# Keep celery worker as minimal as possible to avoid sending messages that we don't really care about
# Also keep prefetch equal to 0 as boto library hangs in an infinite loop when prefetch is set to non-zero
exec celery worker -E -P solo -A f8a_worker.start -Q "${WORKER_QUEUES}" --concurrency=1 --prefetch-multiplier=0 -Ofair --without-gossip --without-mingle --without-heartbeat
