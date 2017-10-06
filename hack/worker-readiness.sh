#!/bin/bash

export F8A_POSTGRES=$(python3 -c 'from f8a_worker.defaults import configuration; print(configuration.POSTGRES_CONNECTION)')

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

