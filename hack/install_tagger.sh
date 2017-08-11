#!/usr/bin/env bash
# This is a temporary hack to ensure that desired f8a_tagger is installed.
# TODO: do proper releases and installation from requirements.txt once tagger implementation gets stabilized

set -e

F8A_TAGGER_COMMIT=19d6a97

pip3 install git+https://github.com/fabric8-analytics/fabric8-analytics-tagger@${F8A_TAGGER_COMMIT}
