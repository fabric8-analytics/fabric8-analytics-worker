#!/bin/bash

set -ex

. cico_setup.sh

docker_login

build_image

IMAGE_NAME=$(make get-image-name) ./qa/runtest.sh

push_image
