#!/bin/bash

# fail if smth fails
# the whole env will be running if test suite fails so you can debug
set -e

# for debugging this script, b/c I sometimes get
# unable to prepare context: The Dockerfile (Dockerfile.tests) must be within the build context (.)
set -x

here=$(cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd)

TIMESTAMP="$(date +%F-%H-%M-%S)"

IMAGE_NAME=${IMAGE_NAME:-registry.devshift.net/bayesian/cucos-worker}
TEST_IMAGE_NAME="worker-tests"
POSTGRES_IMAGE_NAME="registry.centos.org/sclo/postgresql-94-centos7:latest"
S3_IMAGE_NAME="minio/minio"
CVEDB_S3_DUMP_IMAGE_NAME="registry.devshift.net/bayesian/cvedb-s3-dump"

CONTAINER_NAME="worker-tests-${TIMESTAMP}"
# we don't want to wipe local "database" container, so we create a custom one just for tests
TESTDB_CONTAINER_NAME="worker-tests-db-${TIMESTAMP}"
TESTS3_CONTAINER_NAME="worker-tests-s3-${TIMESTAMP}"
TESTCVEDB_S3_DUMP_CONTAINER_NAME="worker-tests-cvedb-s3-dump-${TIMESTAMP}"

gc() {
  retval=$?
  # FIXME: make this configurable
  echo "Stopping test containers"
  docker stop ${CONTAINER_NAME} ${TESTDB_CONTAINER_NAME} ${TESTS3_CONTAINER_NAME} ${TESTCVEDB_S3_DUMP_CONTAINER_NAME} || :
  echo "Removing test containers"
  docker rm -v ${CONTAINER_NAME} ${TESTDB_CONTAINER_NAME} ${TESTS3_CONTAINER_NAME} ${TESTCVEDB_S3_DUMP_CONTAINER_NAME} || :
  exit $retval
}

trap gc EXIT SIGINT

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $IMAGE_NAME for testing"
  docker build --tag=$IMAGE_NAME .
fi

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $TEST_IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $TEST_IMAGE_NAME test image"
  docker build -f ./Dockerfile.tests --tag=$TEST_IMAGE_NAME .
fi

echo "Removing database"
docker kill ${TESTDB_CONTAINER_NAME} ${TESTS3_CONTAINER_NAME} || :
docker rm -vf ${TESTDB_CONTAINER_NAME} ${TESTS3_CONTAINER_NAME} || :

echo "Starting/creating containers:"
# first start the database under different name, so that we don't overwrite a non-testing db
# NOTE: we omit pgbouncer while running tests
docker run -d \
    --env-file tests/postgres.env \
    --name ${TESTDB_CONTAINER_NAME} ${POSTGRES_IMAGE_NAME}
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

docker run -d \
    --env-file tests/minio.env \
    --name ${TESTS3_CONTAINER_NAME} \
    ${S3_IMAGE_NAME} server --address :33000 /export
S3_CONTAINER_IP=$(docker inspect --format '{{.NetworkSettings.IPAddress}}' ${TESTS3_CONTAINER_NAME})
S3_ENDPOINT_URL="http://${S3_CONTAINER_IP}:33000"
docker run \
    -e S3_ENDPOINT_URL=${S3_ENDPOINT_URL} \
    --env-file tests/cvedb_s3_dump.env \
    --link=${TESTS3_CONTAINER_NAME} \
    --name ${TESTCVEDB_S3_DUMP_CONTAINER_NAME} ${CVEDB_S3_DUMP_IMAGE_NAME}

echo "Starting test suite"
docker run -t \
  -v "${here}:/f8a_worker:ro,Z" \
  --link=${TESTDB_CONTAINER_NAME} \
  --link=${TESTS3_CONTAINER_NAME} \
  -e PGBOUNCER_SERVICE_HOST=${TESTDB_CONTAINER_NAME} \
  -e S3_ENDPOINT_URL=${S3_ENDPOINT_URL} \
  -e DEPLOYMENT_PREFIX='test' \
  -e WORKER_ADMINISTRATION_REGION='api' \
  -e F8A_UNCLOUDED_MODE='true' \
  --env-file tests/postgres.env \
  --name=${CONTAINER_NAME} \
  ${TEST_IMAGE_NAME} ./hack/exec_tests.sh $@ tests/

docker cp ${CONTAINER_NAME}:/tmp/pylint.log tests/pylint.log

echo "Test suite passed \\o/"
