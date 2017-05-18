#!/bin/bash

set -xe

THISDIR=`dirname $0`

TIMESTAMP="$(date +%F-%H-%M-%S)"
IMAGE_NAME="docker-registry.usersys.redhat.com/bayesian/cucos-worker"
MIGRATIONS_IMAGE_NAME="coreapi-worker-migrations"
POSTGRES_CONTAINER_NAME="coreapi-migrations-postgres-${TIMESTAMP}"
MIGRATIONS_CONTAINER_NAME="coreapi-worker-migrations-${TIMESTAMP}"
POSTGRES_IMAGE_NAME="registry.centos.org/sclo/postgresql-94-centos7:latest"

docker build --pull --tag=$IMAGE_NAME -f ${THISDIR}/../Dockerfile ${THISDIR}/..
docker build -f ${THISDIR}/../Dockerfile.migrations --tag=$MIGRATIONS_IMAGE_NAME ${THISDIR}/..

gc() {
  retval=$?
  echo "Stopping containers"
  docker stop ${POSTGRES_CONTAINER_NAME} ${MIGRATIONS_CONTAINER_NAME} || :
  echo "Removing containers"
  docker rm -v ${POSTGRES_CONTAINER_NAME} ${MIGRATIONS_CONTAINER_NAME} || :
  exit $retval
}

trap gc EXIT SIGINT

docker run -d --env-file=tests/postgres.env --name ${POSTGRES_CONTAINER_NAME} ${POSTGRES_IMAGE_NAME}
NETWORK=`docker inspect --format '{{.NetworkSettings.Networks}}' ${POSTGRES_CONTAINER_NAME} | awk -F '[:[]' '{print $2}'`
sleep 10

# do crazy magic with quotes so that we can pass the command to the migrations image correctly
cmd="alembic upgrade head && alembic"
for i in "$@"; do
  cmd="$cmd '$i'"
done

. tests/postgres.env

#for MAC docker run -t -v `pwd`:/bayesian \
docker run -t -v `readlink -f ${THISDIR}/..`:/f8a_worker:z \
  --link ${POSTGRES_CONTAINER_NAME} \
  --net=${NETWORK} \
  --name=${MIGRATIONS_CONTAINER_NAME} \
  --env=CCS_POSTGRES=postgresql://${POSTGRESQL_USER}:${POSTGRESQL_PASSWORD}@${POSTGRES_CONTAINER_NAME}:5432/${POSTGRESQL_DATABASE} \
  --env=PYTHONPATH=/f8a_worker \
  ${MIGRATIONS_IMAGE_NAME} "$cmd"
