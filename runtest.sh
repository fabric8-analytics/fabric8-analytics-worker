#!/bin/bash

# fail if smth fails
# the whole env will be running if test suite fails so you can debug
set -e

# for debugging this script, b/c I sometimes get
# unable to prepare context: The Dockerfile (Dockerfile.tests) must be within the build context (.)
set -x

here=$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd)

TIMESTAMP="$(date +%F-%H-%M-%S)"
# DB_CONTAINER_NAME="db-lib-tests-${TIMESTAMP}"
CONTAINER_NAME="lib-tests-${TIMESTAMP}"
# we don't want to wipe local "database" container, so we create a custom one just for tests
TESTDB_CONTAINER_NAME="lib-tests-db-${TIMESTAMP}"
IMAGE_NAME="docker-registry.usersys.redhat.com/bayesian/cucos-worker"
TEST_IMAGE_NAME="cucos-lib-tests"
POSTGRES_IMAGE_NAME="registry.centos.org/sclo/postgresql-94-centos7:latest"

gc() {
  retval=$?
  # FIXME: make this configurable
  echo "Stopping test containers"
  docker stop ${CONTAINER_NAME} ${TESTDB_CONTAINER_NAME} || :
  echo "Removing test containers"
  docker rm -v ${CONTAINER_NAME} ${TESTDB_CONTAINER_NAME} || :
  exit $retval
}

trap gc EXIT SIGINT

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $IMAGE_NAME for testing"
  docker build -t docker-registry.usersys.redhat.com/bayesian/cucos-worker .
fi

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $TEST_IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $TEST_IMAGE_NAME test image"
  docker build -f ./Dockerfile.tests --tag=$TEST_IMAGE_NAME .
fi


echo "Remove database"
docker kill $TESTDB_CONTAINER_NAME || :
docker rm -vf $TESTDB_CONTAINER_NAME || :
echo "Starting/creating containers:"
# first start the database under different name, so that we don't overwrite a non-testing db
# NOTE: we omit pgbouncer while running tests
docker run -d --env-file tests/postgres.env --name ${TESTDB_CONTAINER_NAME} ${POSTGRES_IMAGE_NAME}

DB_CONTAINER_IP=$(docker inspect --format '{{.NetworkSettings.IPAddress}}' ${TESTDB_CONTAINER_NAME})

# TODO: this is duplicating code with server's runtest, we should refactor
echo "Waiting for postgres to fully initialize"
set +x
for i in {1..10}; do
  retcode=`curl http://${DB_CONTAINER_IP}:5432 &>/dev/null || echo $?`
  if test "$retcode" == "52"; then
    break
  fi;
  sleep 1
done;
set -x

secrets_file="${here}/hack/secrets.yaml"
if [ -e ${secrets_file} ]; then
    secrets_vol="-v ${secrets_file}:/var/lib/secrets/secrets.yaml:ro,Z"
fi

echo "Starting test suite"
docker run -t \
  -v "${here}:/cucoslib:ro,Z" \
  ${secrets_vol:-} \
  --link=${TESTDB_CONTAINER_NAME} \
  -e PGBOUNCER_SERVICE_HOST=$TESTDB_CONTAINER_NAME \
  -e DEPLOYMENT_PREFIX='test' \
  --env-file tests/postgres.env \
  --name=${CONTAINER_NAME} \
  $TEST_IMAGE_NAME ./hack/exec_tests.sh $@ tests/

docker cp ${CONTAINER_NAME}:/tmp/pylint.log tests/pylint.log

echo "Test suite passed \\o/"
