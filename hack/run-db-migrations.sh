#!/usr/bin/bash

if [ -z "${WORKER_RUN_DB_MIGRATIONS}" ]; then
    echo "WORKER_RUN_DB_MIGRATIONS was not set - this worker will not run database migrations"
    exit 0
fi

export POSTGRESQL_HOST=${PGBOUNCER_SERVICE_HOST:-coreapi-pgbouncer}
export POSTGRESQL_PORT=${PGBOUNCER_SERVICE_PORT:-5432}
export F8A_POSTGRES=postgresql://${POSTGRESQL_USER}:${POSTGRESQL_PASSWORD}@${POSTGRESQL_HOST}:${POSTGRESQL_PORT}/${POSTGRESQL_DATABASE}
# used by psql
export PGPASSWORD=$POSTGRESQL_PASSWORD

set -ex


# try to create DB in Postgres, if it doesn't exist yet
RESULT=1
while (( RESULT != 0 )); do
  echo "Trying to create database..."
  # http://stackoverflow.com/a/36591842
  psql -h "${POSTGRESQL_HOST}" -p "${POSTGRESQL_PORT}" -U "${POSTGRESQL_USER}" -d "${POSTGRESQL_INITIAL_DATABASE}" -tc "SELECT 1 FROM pg_database WHERE datname = '${POSTGRESQL_DATABASE}'" | grep -q 1 || psql -h "${POSTGRESQL_HOST}" -p "${POSTGRESQL_PORT}" -U "${POSTGRESQL_USER}" -d "${POSTGRESQL_INITIAL_DATABASE}" -c "CREATE DATABASE ${POSTGRESQL_DATABASE}"
  RESULT=$?
  if (( RESULT == 0 )); then
    echo "Database created"
  else
    echo "Failed creating database, sleeping for 10 seconds"
    sleep 10
  fi
done

# run alembic migrations
pushd "${ALEMBIC_DIR}"
  export MIGRATE_ONLY=1
  alembic upgrade head
popd
