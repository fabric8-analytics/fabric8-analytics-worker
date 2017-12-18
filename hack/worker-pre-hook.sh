#!/usr/bin/bash
# This script is run as a pre-hook only once per deployment

set -e

# We need *only one* worker pod to run db migrations and configure SQS queues.
# For now we use the same WORKER_RUN_DB_MIGRATIONS env variable for both,
# because a pod would either do both operations or none.
if [ -z "${WORKER_RUN_DB_MIGRATIONS}" ]; then
    echo "WORKER_RUN_DB_MIGRATIONS was not set - this worker will neither run database migrations nor configure queue attributes"
    exit 0
fi

/alembic/run-db-migrations.sh

# Fill in $WORKER_QUEUES
source worker-queues-env.sh

# Configure queue attributes
queue_conf.py "${WORKER_QUEUES}"
