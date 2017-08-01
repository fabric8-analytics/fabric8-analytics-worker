#!/usr/bin/sh -e
# We need postgresql-devel and python3-devel for psycopg2 listed in f8a_worker/requirements.txt
# We cannot use requests from PyPI since it does not allow us to use own certificates
# python3-pycurl is needed for Amazon SQS (boto lib), we need Fedora's rpm - installing it from pip results in NSS errors
REQUIREMENTS_TXT='postgresql-devel python34-devel libxml2-devel libxslt-devel python34-requests python34-pycurl'
# f8a_worker/process.py requirements
REQUIRES='git /usr/bin/npm unzip tar file findutils koji rpmdevtools nodejs-packaging wget'
# DigesterTask
REQUIRES_TASK='ssdeep'
# github-linguist (languages)
# LINGUIST='rubygems ruby-devel'
# oscryptocatcher check from copr repo
# OSCRYPTOCATCHER='oscryptocatcher'
# covscan
CSMOCK_TASK_DEPS="csmock"
# blackduck
BD_DEPS="which java"
# there's no python3 version of brew utils yet
BREWUTILS="python2-brewutils"
# mercator-go
MERCATOR="mercator"
# CodeMetricsTask - it requires python-pip, since we'll be installing mccabe for both Python 2 and 3
CODE_METRICS="cloc python-pip"
# Install all RPM deps
yum install -y --setopt=tsflags=nodocs ${REQUIREMENTS_TXT} ${REQUIRES} \
                ${REQUIRES_TASK} ${LINGUIST} \
                ${OSCRYPTOCATCHER} ${CSMOCK_TASK_DEPS} \
                ${BD_DEPS} ${BREWUTILS} ${MERCATOR} ${CODE_METRICS}
