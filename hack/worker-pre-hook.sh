#!/usr/bin/bash
# This script is run as a pre-hook only once per deployment

set -e

/alembic/run-db-migrations.sh

# Fill in $WORKER_QUEUES
source worker-queues-env.sh

# Configure queue attributes
queue_conf.py "${WORKER_QUEUES}"
