#!/usr/bin/bash -e

set -x
oc whoami
oc project
set +x

function oc_process_apply() {
  echo -e "\n Processing template - $1 ($2) \n"
  oc process -f $1 $2 | oc apply -f -
}

here=`dirname $0`
template="${here}/template.yaml"

oc_process_apply "$template" "-v WORKER_ADMINISTRATION_REGION=ingestion"
oc_process_apply "$template" "-v WORKER_ADMINISTRATION_REGION=api"

