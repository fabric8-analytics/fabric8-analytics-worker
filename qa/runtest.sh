#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"

pushd "${SCRIPT_DIR}/.." > /dev/null

# fail if smth fails
# the whole env will be running if test suite fails so you can debug
set -e

# for debugging this script, b/c I sometimes get
# unable to prepare context: The Dockerfile (Dockerfile.tests) must be within the build context (.)
set -x

here=$(pwd)

TIMESTAMP="$(date +%F-%H-%M-%S)"

IMAGE_NAME=${IMAGE_NAME:-openshiftio/bayesian-cucos-worker}
TEST_IMAGE_NAME="worker-tests"
POSTGRES_IMAGE_NAME="registry.centos.org/centos/postgresql-94-centos7:latest"
S3_IMAGE_NAME="quay.io/ricardbejarano/minio"

CONTAINER_NAME="worker-tests-${TIMESTAMP}"
# we don't want to wipe local "database" container, so we create a custom one just for tests
TESTDB_CONTAINER_NAME="worker-tests-db-${TIMESTAMP}"
TESTS3_CONTAINER_NAME="worker-tests-s3-${TIMESTAMP}"
DOCKER_NETWORK="F8aWorkerTest"

check_python_version() {
    python3 tools/check_python_version.py 3 6
}

gc() {
  retval=$?
  # FIXME: make this configurable
  echo "Stopping test containers"
  docker stop "${CONTAINER_NAME}" "${TESTDB_CONTAINER_NAME}" "${TESTS3_CONTAINER_NAME}" || :
  echo "Removing test containers"
  docker rm -v "${CONTAINER_NAME}" "${TESTDB_CONTAINER_NAME}" "${TESTS3_CONTAINER_NAME}" || :
  echo "Removing network ${DOCKER_NETWORK}"
  docker network rm "${DOCKER_NETWORK}" || :
  exit $retval
}

check_python_version

trap gc EXIT SIGINT

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $IMAGE_NAME for testing"
  docker build --tag="$IMAGE_NAME" .
fi

if [ "$REBUILD" == "1" ] || \
     !(docker inspect $TEST_IMAGE_NAME > /dev/null 2>&1); then
  echo "Building $TEST_IMAGE_NAME test image"
  docker build -f ./Dockerfile.tests --tag=$TEST_IMAGE_NAME .
fi

echo "Removing database"
docker kill "${TESTDB_CONTAINER_NAME}" "${TESTS3_CONTAINER_NAME}" || :
docker rm -vf "${TESTDB_CONTAINER_NAME}" "${TESTS3_CONTAINER_NAME}" || :

echo "Creating network ${DOCKER_NETWORK}"
docker network create ${DOCKER_NETWORK}

echo "Starting/creating containers:"
# first start the database under different name, so that we don't overwrite a non-testing db
# NOTE: we omit pgbouncer while running tests
docker run -d \
    --env-file tests/postgres.env \
    --network ${DOCKER_NETWORK} \
    --name "${TESTDB_CONTAINER_NAME}" "${POSTGRES_IMAGE_NAME}"
DB_CONTAINER_IP=$(docker inspect --format "{{.NetworkSettings.Networks.${DOCKER_NETWORK}.IPAddress}}" ${TESTDB_CONTAINER_NAME})

# TODO: this is duplicating code with server's runtest, we should refactor
echo "Waiting for postgres to fully initialize"
for i in {1..10}; do
  set +e
  docker exec -t "${TESTDB_CONTAINER_NAME}" bash -c pg_isready
  if [[ "$?" == "0" ]]; then
    break
  fi;
  set -e
  sleep 2
done;
echo "Postgres is ready.."

docker run -d \
    --env-file tests/minio.env \
    --name "${TESTS3_CONTAINER_NAME}" \
    --network "${DOCKER_NETWORK}" \
    ${S3_IMAGE_NAME} server --address :33000 /export
S3_CONTAINER_IP=$(docker inspect --format "{{.NetworkSettings.Networks.${DOCKER_NETWORK}.IPAddress}}" ${TESTS3_CONTAINER_NAME})
S3_ENDPOINT_URL="http://${S3_CONTAINER_IP}:33000"

echo "Starting test suite"
docker run -t \
  -v "${here}:/f8a_worker:rw,Z" \
  --network "${DOCKER_NETWORK}" \
  -u 9007 \
  -e PGBOUNCER_SERVICE_HOST="${TESTDB_CONTAINER_NAME}" \
  -e S3_ENDPOINT_URL="${S3_ENDPOINT_URL}" \
  -e DEPLOYMENT_PREFIX='test' \
  -e WORKER_ADMINISTRATION_REGION='api' \
  -e F8A_UNCLOUDED_MODE='true' \
  -e SENTRY_DSN='' \
  --env-file tests/postgres.env \
  --name="${CONTAINER_NAME}" \
  ${TEST_IMAGE_NAME} /f8a_worker/hack/exec_tests.sh $@ /f8a_worker/tests/
popd > /dev/null

echo "Test suite passed \\o/"