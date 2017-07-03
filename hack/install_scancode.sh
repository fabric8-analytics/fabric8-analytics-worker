#!/usr/bin/sh -ex

# We use development (master) from git repo because 2.0.0rc2 doesn't have fixes we need.
# But we can stabilize to final 2.0.0 once it's released - see the commented code below.

cd /opt
git clone --depth 1 https://github.com/nexB/scancode-toolkit.git
cd scancode-toolkit

# scancode-toolkit has broken dependencies. This commit it working
# Workaround until upstream is fixed
git checkout 1fea769

#RELEASE='2.0.0'
#RC="rc2"
#mkdir -p $SCANCODE_PATH
#cd ${SCANCODE_PATH}
#wget -q "https://github.com/nexB/scancode-toolkit/releases/download/v${RELEASE}.${RC}/scancode-toolkit-${RELEASE}${RC}.zip" -O "scancode-toolkit.zip"
#unzip -q "scancode-toolkit.zip"
#rm -f "scancode-toolkit.zip"
#mv "scancode-toolkit-${RELEASE}${RC}"/* .
#rm -rf "scancode-toolkit-${RELEASE}${RC}/"

# Build license detection index (.cache/)
./scancode --quiet CHANGELOG.rst
# ScanCode running as non-root fails on deleting this directory
rm -rf .cache/scan_results_caches/
# Make sure that group & others can execute in bin/ and write to .cache/
# Can be set more fine grained, but it's OK for now
chmod -R a+rwX .
