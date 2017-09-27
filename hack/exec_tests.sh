#!/usr/bin/bash

set -e
# we need no:cacheprovider, otherwise pytest will try to write to directory .cache which is in /usr under unprivileged
# user and will cause exception
py.test -p no:cacheprovider -vv $@

echo "Running pylint..."
pylint ./f8a_worker/ > /tmp/pylint.log || exit 0
