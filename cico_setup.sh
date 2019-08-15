#!/bin/bash -ex

REGISTRY="quay.io"

load_jenkins_vars() {
    if [ -e "jenkins-env.json" ]; then
        eval "$(./env-toolkit load -f jenkins-env.json \
                DEVSHIFT_TAG_LEN \
                QUAY_USERNAME \
                QUAY_PASSWORD \
                JENKINS_URL \
                GIT_BRANCH \
                GIT_COMMIT \
                BUILD_NUMBER \
                ghprbSourceBranch \
                ghprbActualCommit \
                BUILD_URL \
                ghprbPullId)"
    fi
}
docker_login() {
    if [ -n "${QUAY_USERNAME}" -a -n "${QUAY_PASSWORD}" ]; then
        docker login -u "${QUAY_USERNAME}" -p "${QUAY_PASSWORD}" "${REGISTRY}"
    else
        echo "Could not login, missing credentials for the registry"
        exit 1
    fi
}

prep() {
    # workaround for https://bugs.centos.org/view.php?id=16337 #
    echo -e "exclude=mirror.ci.centos.org" >> /etc/yum/pluginconf.d/fastestmirror.conf

    yum -y update
    yum -y install docker git
    yum -y install epel-release
    yum -y install python36-pip python36 python36-virtualenv
    systemctl start docker
}

build_image() {
    # build image and tests
    make docker-build-tests
}

tag_push() {
    local target=$1
    local source=$2
    docker tag "${source}" "${target}"
    docker push "${target}"
}

push_image() {
    local image_name
    local short_commit

    image_name=$(make get-image-name-base)
    short_commit=$(git rev-parse --short=$DEVSHIFT_TAG_LEN HEAD)

    if [ -n "${ghprbPullId}" ]; then
        # PR build
        pr_id="SNAPSHOT-PR-${ghprbPullId}"
        tag_push "${image_name}:${pr_id}" "${image_name}"
        tag_push "${image_name}:${pr_id}-${short_commit}" "${image_name}"
    else
        # master branch build
        tag_push "${image_name}:latest" "${image_name}"
        tag_push "${image_name}:${short_commit}" "${image_name}"
    fi

    echo 'CICO: Image pushed, ready to update deployed app'
}

load_jenkins_vars
prep
