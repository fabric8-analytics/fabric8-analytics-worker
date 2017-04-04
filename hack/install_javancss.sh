#!/usr/bin/sh -ex

JAVANCSS_VERSION="32.53"
JAVANCSS_FILENAME="javancss-${JAVANCSS_VERSION}"
JAVANCSS_URL="http://www.kclee.de/clemens/java/javancss/${JAVANCSS_FILENAME}.zip "

mkdir -p $JAVANCSS_PATH
cd $JAVANCSS_PATH
curl "${JAVANCSS_URL}" -o "${JAVANCSS_FILENAME}.zip"
unzip "${JAVANCSS_FILENAME}.zip"
rm "${JAVANCSS_FILENAME}.zip"
mv "${JAVANCSS_FILENAME}"/* .
rm -rf "${JAVANCSS_FILENAME:?}/"
