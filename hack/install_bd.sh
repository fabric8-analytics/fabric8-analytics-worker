#!/usr/bin/sh -e

mkdir -p $BLACKDUCK_PATH && cd $BLACKDUCK_PATH
curl -O https://eng-hub.blackducksoftware.com/download/scan.cli.zip
unzip scan.cli.zip
rm scan.cli.zip