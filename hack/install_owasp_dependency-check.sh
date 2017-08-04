#!/usr/bin/sh -ex

RELEASE='2.1.0'
NAME='dependency-check'

# sanity check
if [[ -z $OWASP_DEP_CHECK_PATH ]]; then
    echo "OWASP_DEP_CHECK_PATH not set"
    exit 1
fi

# download
mkdir -p $OWASP_DEP_CHECK_PATH
cd ${OWASP_DEP_CHECK_PATH}
wget -q "https://bintray.com/jeremy-long/owasp/download_file?file_path=dependency-check-${RELEASE}-release.zip" -O "${NAME}.zip"
unzip -q "${NAME}.zip"
rm -f "${NAME}.zip"
mv "${NAME}"/* .
mkdir --mode 775 "data/"
rm -rf "${NAME:?}/"
