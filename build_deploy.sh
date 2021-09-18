#!/bin/bash
set -exv

BASE_IMG="bayesian-cucos-worker"
QUAY_IMAGE="quay.io/app-sre/${BASE_IMG}"
IMG="${BASE_IMG}:latest"

GIT_HASH=`git rev-parse --short=7 HEAD`

# build the image
docker build  --no-cache \
              --force-rm \
              -t ${IMG}  \
              -f ./Dockerfile.app-sre .

docker login  -u="$QUAY_USER" -p="$QUAY_TOKEN" quay.io
# push the image
docker tag ${IMG} "${QUAY_IMAGE}:latest"
docker push "${QUAY_IMAGE}:latest"

docker tag ${IMG} "${QUAY_IMAGE}:${GIT_HASH}"
docker push "${QUAY_IMAGE}:${GIT_HASH}"

#skopeo copy --dest-creds "${QUAY_USER}:${QUAY_TOKEN}" \
#    "docker-daemon:${IMG}" \
#    "docker://${QUAY_IMAGE}:latest"

#skopeo copy --dest-creds "${QUAY_USER}:${QUAY_TOKEN}" \
#    "docker-daemon:${IMG}" \
#    "docker://${QUAY_IMAGE}:${GIT_HASH}"
