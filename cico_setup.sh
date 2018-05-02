#!/bin/bash -ex

REGISTRY="push.registry.devshift.net"

load_jenkins_vars() {
    if [ -e "jenkins-env" ]; then
        cat jenkins-env \
          | grep -E "(DEVSHIFT_TAG_LEN|DEVSHIFT_USERNAME|DEVSHIFT_PASSWORD|JENKINS_URL|GIT_BRANCH|GIT_COMMIT|BUILD_NUMBER|ghprbSourceBranch|ghprbActualCommit|BUILD_URL|ghprbPullId)=" \
          | sed 's/^/export /g' \
          > ~/.jenkins-env
        source ~/.jenkins-env
    fi
}

docker_login() {
    if [ -n "${DEVSHIFT_USERNAME}" -a -n "${DEVSHIFT_PASSWORD}" ]; then
        docker login -u ${DEVSHIFT_USERNAME} -p ${DEVSHIFT_PASSWORD} ${REGISTRY}
    else
        echo "Could not login, missing credentials for the registry"
        exit 1
    fi
}

prep() {
    yum -y update
    yum -y install docker git
    systemctl start docker
}

build_image() {
    # build image and tests
    make docker-build-tests
}

tag_push() {
    local target=$1
    local source=$2
    docker tag ${source} ${target}
    docker push ${target}
}

push_image() {
    local image_name
    local image_repository
    local short_commit
    image_name=$(make get-image-name)
    image_repository=$(make get-image-repository)
    short_commit=$(git rev-parse --short=7 HEAD)

    if [ "$TARGET" = "rhel" ]; then
        IMAGE_URL="${REGISTRY}/osio-prod/${image_repository}"
    else
        IMAGE_URL="${REGISTRY}/${image_repository}"
    fi

    if [ -n "${ghprbPullId}" ]; then
        # PR build
        pr_id="SNAPSHOT-PR-${ghprbPullId}"
        tag_push ${IMAGE_URL}:${pr_id} ${image_name}
        tag_push ${IMAGE_URL}:${pr_id}-${short_commit} ${image_name}
    else
        # master branch build
        tag_push ${IMAGE_URL}:latest ${image_name}
        tag_push ${IMAGE_URL}:${short_commit} ${image_name}
    fi

    echo 'CICO: Image pushed, ready to update deployed app'
}

load_jenkins_vars
prep
