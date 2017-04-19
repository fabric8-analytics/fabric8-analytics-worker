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

if [[ $PTH_ENV ]]; then
  deployment_prefix=$PTH_ENV
else
  deployment_prefix=$(oc whoami)
fi
s3_bucket_for_analyses=${deployment_prefix}-${S3_BUCKET_FOR_ANALYSES:-bayesian-core-data}

oc_process_apply "$template" "-v DEPLOYMENT_PREFIX=${deployment_prefix} -v WORKER_ADMINISTRATION_REGION=ingestion -v S3_BUCKET_FOR_ANALYSES=${s3_bucket_for_analyses}"
oc_process_apply "$template" "-v DEPLOYMENT_PREFIX=${deployment_prefix} -v WORKER_ADMINISTRATION_REGION=api -v S3_BUCKET_FOR_ANALYSES=${s3_bucket_for_analyses}"

