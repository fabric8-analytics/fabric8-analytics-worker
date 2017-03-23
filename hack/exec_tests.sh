#!/usr/bin/bash

set -e
DIR=$(dirname "${BASH_SOURCE[0]}")
source $DIR/env.sh

# we need no:cacheprovider, otherwise pytest will try to write to directory .cache which is in /usr under unprivileged
# user and will cause exception
py.test -p no:cacheprovider -vv $@

echo "Running pylint..."
pylint ./cucoslib/ > /tmp/pylint.log || exit 0
