FROM registry.centos.org/centos/centos:7
MAINTAINER Pavel Odvody <podvody@redhat.com>, or Tomas Tomecek <ttomecek@redhat.com>, or Jiri Popelka <jpopelka@redhat.com>

ENV LANG=en_US.UTF-8 \
    BLACKDUCK_PATH='/opt/blackduck/' \
    JAVANCSS_PATH='/opt/javancss/' \
    OWASP_DEP_CHECK_PATH='/opt/dependency-check/' \
    SCANCODE_PATH='/opt/scancode-toolkit/' \
    # place where to download & unpack artifacts
    WORKER_DATA_DIR='/var/lib/f8a_worker/worker_data' \
    # home directory
    HOME='/workdir' \
    # place for alembic migrations
    ALEMBIC_DIR='/alembic'

CMD ["/usr/bin/workers.sh"]

# Cache friendly dependency specifications:
#   - deps are listed in text files or scripts inside the lib/ dir
#   - individual files are copied in during image build
#   - changes in minimum and/or pinned versions will invalidate the cache
RUN mkdir -p /tmp/install_deps

# https://copr.fedorainfracloud.org/coprs/jpopelka/mercator/
# https://copr.fedorainfracloud.org/coprs/jpopelka/python-brewutils/
COPY hack/_copr_jpopelka-mercator.repo hack/_copr_jpopelka-python-brewutils.repo /etc/yum.repos.d/

# Install RPM dependencies
COPY hack/install_deps_rpm.sh /tmp/install_deps/
RUN yum install -y epel-release && \
    yum install -y python34-pip openssl ruby-devel libicu-devel gcc-c++ cmake postgresql && \
    /tmp/install_deps/install_deps_rpm.sh && \
    yum clean all

# Install binwalk, the pip package is broken, following docs from github.com/devttys0/binwalk
RUN mkdir /tmp/binwalk/ && \
    curl -L https://github.com/devttys0/binwalk/archive/v2.1.1.tar.gz | tar xz -C /tmp/binwalk/ --strip-components 1 && \
    python /tmp/binwalk/setup.py install && \
    rm -rf /tmp/binwalk/

# Install non-Mercator python native deps
COPY hack/pip-requirements.txt /tmp/install_deps/

# Fixes: http://stackoverflow.com/questions/14296531
RUN pip3 install --upgrade pip && pip install --upgrade wheel && \
    pip3 install -r /tmp/install_deps/pip-requirements.txt && \
    pip3 install alembic psycopg2 git+git://github.com/msrb/kombu@sqs-conn#egg=kombu

# Install github-linguist rubygem
RUN gem install --no-document github-linguist -v 5.0.2

# Install javascript deps
COPY hack/install_deps_npm.sh /tmp/install_deps/
RUN /tmp/install_deps/install_deps_npm.sh

# Install BlackDuck CLI
#COPY hack/install_bd.sh /tmp/install_deps/
#RUN /tmp/install_deps/install_bd.sh

# Install JavaNCSS for code metrics
COPY hack/install_javancss.sh /tmp/install_deps/
RUN /tmp/install_deps/install_javancss.sh

# Install OWASP dependency-check cli for security scan of jar files
COPY hack/install_owasp_dependency-check.sh /tmp/install_deps/
RUN /tmp/install_deps/install_owasp_dependency-check.sh

# Install ScanCode-toolkit for license scan
COPY hack/install_scancode.sh /tmp/install_deps/
RUN /tmp/install_deps/install_scancode.sh

# Install dependencies required in both Python 2 and 3 versions
COPY ./hack/py23requirements.txt /tmp/install_deps/
RUN pip2 install -r /tmp/install_deps/py23requirements.txt
RUN pip3 install -r /tmp/install_deps/py23requirements.txt

# Import RH CA cert
COPY hack/import_RH_CA_cert.sh /tmp/install_deps/
RUN /tmp/install_deps/import_RH_CA_cert.sh

# Import BlackDuck Hub CA cert
#COPY hack/import_BD_CA_cert.sh /tmp/install_deps/
#RUN /tmp/install_deps/import_BD_CA_cert.sh

# Make sure random user has place to store files
RUN mkdir -p ${HOME} ${WORKER_DATA_DIR} ${ALEMBIC_DIR}/alembic/ && \
    chmod 777 ${HOME} ${WORKER_DATA_DIR}
WORKDIR ${HOME}

# You don't want to repeat all the above when changing something in repo
# while it's okay to rerun this \/
RUN mkdir -p /tmp/f8a_worker

COPY requirements.txt /tmp/f8a_worker
RUN cd /tmp/f8a_worker && \
    pip3 install -r requirements.txt

COPY alembic.ini hack/run-db-migrations.sh ${ALEMBIC_DIR}/
COPY alembic/ ${ALEMBIC_DIR}/alembic

# Install f8a_worker
COPY ./ /tmp/f8a_worker
RUN cd /tmp/f8a_worker && pip3 install .

# Make sure there are no root-owned files and directories in the home directory,
# as this directory can be used by non-root user at runtime.
RUN find ${HOME} -mindepth 1 -delete

# A temporary hack to keep Selinon up2date
COPY hack/update_selinon.sh /tmp/
RUN sh /tmp/update_selinon.sh

# Not-yet-upstream-released patches
RUN mkdir -p /tmp/install_deps/patches/
COPY hack/patches/* /tmp/install_deps/patches/
COPY hack/patches/* /tmp/install_deps/patches/
COPY hack/apply_patches.sh /tmp/install_deps/
# Apply patches here to be able to patch selinon as well
RUN /tmp/install_deps/apply_patches.sh

RUN pip3 uninstall -y protobuf && pip3 install packaging appdirs && pip3 install --upgrade --no-binary :all: protobuf==3.3.0
