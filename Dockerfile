FROM registry.devshift.net/fabric8-analytics/f8a-worker-base:2cfa3f2

ENV LANG=en_US.UTF-8 \
    # place where to download & unpack artifacts
    WORKER_DATA_DIR='/var/lib/f8a_worker/worker_data' \
    # home directory
    HOME='/workdir' \
    # place for alembic migrations
    ALEMBIC_DIR='/alembic'

# Install little pcp pmcd server for metrics collection
# would prefer only pmcd, and not the /bin/pm*tools etc.
COPY pcp.repo /etc/yum.repos.d/pcp.repo
RUN yum install -y pcp && yum clean all && \
    mkdir -p /etc/pcp /var/run/pcp /var/lib/pcp /var/log/pcp  && \
    chgrp -R root /etc/pcp /var/run/pcp /var/lib/pcp /var/log/pcp && \
    chmod -R g+rwX /etc/pcp /var/run/pcp /var/lib/pcp /var/log/pcp
COPY ./worker+pmcd.sh /worker+pmcd.sh
EXPOSE 44321
CMD ["/worker+pmcd.sh"]

# Make sure random user has place to store files
RUN mkdir -p ${HOME} ${WORKER_DATA_DIR} ${ALEMBIC_DIR}/alembic/ && \
    chmod 777 ${HOME} ${WORKER_DATA_DIR}
WORKDIR ${HOME}

RUN mkdir -p /tmp/f8a_worker
COPY requirements.txt /tmp/f8a_worker
# Install google.protobuf from source
# https://github.com/fabric8-analytics/fabric8-analytics-worker/issues/261
# https://github.com/google/protobuf/issues/1296
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

# A temporary hack to keep tagger up2date
# Do not move this line before HOME clean up, we need downloaded external data baked in resulting image.
COPY hack/install_tagger.sh /tmp/
RUN sh /tmp/install_tagger.sh
