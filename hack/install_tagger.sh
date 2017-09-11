#!/usr/bin/env bash
# This is a temporary hack to ensure that desired f8a_tagger is installed.
# TODO: do proper releases and installation from requirements.txt once tagger implementation gets stabilized

set -e

F8A_TAGGER_COMMIT=3eac4b7

# tagger uses python wrapper above libarchive so install it explicitly
yum install -y libarchive
pip3 install --upgrade git+https://github.com/fabric8-analytics/fabric8-analytics-tagger@${F8A_TAGGER_COMMIT}
# Install external resources needed for automated tagging.
python3 -c 'import f8a_tagger; f8a_tagger.prepare()'
