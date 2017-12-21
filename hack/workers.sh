#!/usr/bin/env bash
# Worker startup script

# Fill in $WORKER_QUEUES
source worker-queues-env.sh

# Keep celery worker as minimal as possible to avoid sending messages that we don't really care about
exec celery worker -P solo -A f8a_worker.start -Q "${WORKER_QUEUES}" --concurrency=1 --prefetch-multiplier=128 -Ofair --without-gossip --without-mingle --without-heartbeat
