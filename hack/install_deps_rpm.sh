#!/usr/bin/sh -e

# Required by Dockerfile or any built-time script in hack/
BUILD="python34-pip python2-pip wget"
# relics of the past, no idea why we used them, can be removed eventually
UNKNOWN_BUILD="libicu-devel gcc-c++ cmake"

# We need postgresql-devel and python3-devel for psycopg2 listed in f8a_worker/requirements.txt
# We cannot use requests from PyPI since it does not allow us to use own certificates
# python3-pycurl is needed for Amazon SQS (boto lib), we need Fedora's rpm - installing it from pip results in NSS errors
REQUIREMENTS_TXT='postgresql-devel python34-devel libxml2-devel libxslt-devel python34-requests python34-pycurl'

# hack/run-db-migrations.sh
DB_MIGRATIONS='postgresql'

# f8a_worker/process.py
PROCESS_PY='git unzip tar file findutils npm'

# DigesterTask
DIGESTER='ssdeep'

# github-linguist (languages)
# LINGUIST='rubygems ruby-devel'

# oscryptocatcher check from copr repo
# OSCRYPTOCATCHER='oscryptocatcher'

# covscan
# CSMOCK_TASK_DEPS="csmock"

# blackduck
# BD_DEPS="openssl which java"

# there's no python3 version of brew utils yet
BREWUTILS="python2-brewutils"

# mercator-go
MERCATOR="mercator"

# CodeMetricsTask - it requires python-pip, since we'll be installing mccabe for both Python 2 and 3
# CODE_METRICS="cloc python-pip"

# OWASP dependency-check used by CVEcheckerTask
DEPENDENCY_CHECK="which"

# relics of the past, no idea why we used them, can be removed eventually
UNKNOWN="koji rpmdevtools nodejs-packaging"

# Install all RPM deps
yum install -y --setopt=tsflags=nodocs ${BUILD} ${REQUIREMENTS_TXT} \
                ${DB_MIGRATIONS} ${PROCESS_PY} \
                ${DIGESTER} ${LINGUIST} \
                ${OSCRYPTOCATCHER} ${CSMOCK_TASK_DEPS} \
                ${BD_DEPS} ${BREWUTILS} ${MERCATOR} ${CODE_METRICS} \
                ${DEPENDENCY_CHECK}
