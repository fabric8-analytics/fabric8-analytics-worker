FROM registry.devshift.net/fabric8-analytics/f8a-worker-base:4a22b88

ENV LANG=en_US.UTF-8 \
    # place where to download & unpack artifacts
    WORKER_DATA_DIR='/var/lib/f8a_worker/worker_data' \
    # home directory
    HOME='/workdir' \
    # place for alembic migrations
    ALEMBIC_DIR='/alembic' \
    # place for graph schema creations
    GRAPH_DIR='/graph'

CMD ["/usr/bin/workers.sh"]

# Make sure random user has place to store files
RUN mkdir -p ${HOME} ${WORKER_DATA_DIR} ${ALEMBIC_DIR}/alembic/ ${GRAPH_DIR} && \
    chmod 777 ${HOME} ${WORKER_DATA_DIR}
WORKDIR ${HOME}

RUN mkdir -p /tmp/f8a_worker
COPY requirements.txt /tmp/f8a_worker
# Install google.protobuf from source
# https://github.com/fabric8-analytics/fabric8-analytics-worker/issues/261
# https://github.com/google/protobuf/issues/1296
RUN cd /tmp/f8a_worker && \
    pip3 install --upgrade --no-binary :all: protobuf==3.3.0 && \
    pip3 install -r requirements.txt

COPY alembic.ini hack/run-db-migrations.sh ${ALEMBIC_DIR}/
COPY alembic/ ${ALEMBIC_DIR}/alembic
COPY hack/create_graph_schema.py hack/schema.groovy ${GRAPH_DIR}/

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

# Not-yet-upstream-released patches
RUN mkdir -p /tmp/install_deps/patches/
COPY hack/patches/* /tmp/install_deps/patches/
RUN /tmp/install_deps/patches/apply_patches.sh
