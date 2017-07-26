#!/usr/bin/bash -e

HERE=$(dirname $0)

patch -p1 --directory /usr/lib64/python3.4/site-packages/ < "${HERE}/0001-PyGithub.patch"

patch -p1 --directory "${SCANCODE_PATH}" < "${HERE}/scancode_ignore_binary.patch"

exit 0
