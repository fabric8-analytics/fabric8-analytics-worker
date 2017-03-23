#!/usr/bin/sh -e
# depsolving
REQUIRES_NPM='semver-ranger'
# CodeMetricsTask
CODEMETRICS_NPM='complexity-report'

for package in ${REQUIRES_NPM} ${CODEMETRICS_NPM}; do
    npm install -g ${package}
done
