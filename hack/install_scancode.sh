#!/usr/bin/sh -ex

# sanity check
if [ ! $SCANCODE_PATH ]; then
    echo "SCANCODE_PATH not set"
    exit 1
fi

# Uncomment if you want to use develop branch of upstream repo instead of $RELEASE
#cd /opt
#git clone --depth 1 https://github.com/nexB/scancode-toolkit.git
#cd scancode-toolkit

RELEASE='2.0.1'
mkdir -p $SCANCODE_PATH
cd ${SCANCODE_PATH}
wget -q "https://github.com/nexB/scancode-toolkit/releases/download/v${RELEASE}/scancode-toolkit-${RELEASE}.zip" -O "scancode-toolkit.zip"
unzip -q "scancode-toolkit.zip"
rm -f "scancode-toolkit.zip"
mv "scancode-toolkit-${RELEASE}"/* .
rm -rf "scancode-toolkit-${RELEASE}/"

# Build license detection index (.cache/)
./scancode --quiet CHANGELOG.rst
# ScanCode running as non-root fails on deleting this directory
rm -rf .cache/scan_results_caches/
# Make sure that group & others can execute in bin/ and write to .cache/
# Can be set more fine grained, but it's OK for now
chmod -R a+rwX .
