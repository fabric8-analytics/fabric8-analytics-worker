#!/usr/bin/env bash
# This script is used as a liveness probe - desired node in the cluster should reply with PONG, so we are sure that
# the node is active and alive.

set -e
DIR=$(dirname "${BASH_SOURCE[0]}")

NODE_NAME="celery@${HOSTNAME}"
BROKER_URL=$(python3 -c "from f8a_worker.celery_settings import CelerySettings; print(CelerySettings.broker_url)")

# Temporary always true, see issue 366
: celery inspect -A f8a_worker.start -b "${BROKER_URL}" ping -d "${NODE_NAME}"
