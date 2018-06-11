#!/usr/bin/bash

set -e
DIR=$(dirname "${BASH_SOURCE[0]}")

echo "*****************************************"
echo "*** Cyclomatic complexity measurement ***"
echo "*****************************************"
radon cc -s -a -i venv /f8a_worker/f8a_worker $@

echo "*****************************************"
echo "*** Maintainability Index measurement ***"
echo "*****************************************"
radon mi -s -i venv /f8a_worker/f8a_worker $@

echo "*****************************************"
echo "*** Unit tests ***"
echo "*****************************************"

# we need no:cacheprovider, otherwise pytest will try to write to directory .cache which is in /usr under unprivileged
# user and will cause exception
py.test -p no:cacheprovider --cov=/f8a_worker/f8a_worker --cov-report term-missing --cov-report xml -vv "$@"

# this is necessary - codecov expect proper git repo
cp -r /f8a_worker/.git ./

codecov --token=04560f69-79e3-48a3-9731-92c9e767a2ff
