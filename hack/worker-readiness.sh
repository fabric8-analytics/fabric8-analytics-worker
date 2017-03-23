#!/bin/bash

export CCS_POSTGRES=postgresql://${POSTGRESQL_USER}:${POSTGRESQL_PASSWORD}@${PGBOUNCER_SERVICE_HOST:-coreapi-pgbouncer}:${PGBOUNCER_SERVICE_PORT:-5432}/${POSTGRESQL_DATABASE}

set -ex

pushd ${ALEMBIC_DIR}
wanted=$(alembic heads | grep '(head)' | awk '{ print $1 }')
current=$(alembic current | grep '(head)' | awk '{ print $1 }')
popd

if [ -z "${wanted}" ]; then
    echo "unable to determine alembic head..."
    exit 1
fi

if [ "${wanted}" != "${current}" ]; then
    echo "The DB version should be ${wanted}, but is ${current}. Maybe DB migration is still in progress/failed?"
    exit 1
fi

echo "We are ready to roll! :)"

