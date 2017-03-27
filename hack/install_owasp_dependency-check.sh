#!/usr/bin/sh -e

RELEASE='1.4.5'
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
rm -rf "${NAME}"/

# to update CVE/CPE data files we need to actually scan some jar
JUNITVER='4.12'
curl "http://central.maven.org/maven2/junit/junit/${JUNITVER}/junit-${JUNITVER}.jar" -o junit-${JUNITVER}.jar
echo "Running Dependency-Check to update CVE/CPE data files"
bin/dependency-check.sh --format XML --project test --scan junit-${JUNITVER}.jar || :
# to be able to update the DB later as non-root:root
chmod -R u+rwX,g+rwX data/
rm -f junit-${JUNITVER}.jar dependency-check-report.xml
