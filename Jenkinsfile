#!/usr/bin/env groovy
@Library('github.com/msrb/cicd-pipeline-helpers')
def commitId
node('docker') {

    def image = docker.image('bayesian/cucos-worker')


    stage('Checkout') {
        checkout scm
        commitId = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
        dir('openshift') {
            stash name: 'template', includes: 'template.yaml'
        }
    }

    stage('Build') {
        dockerCleanup()
        docker.build(image.id, '--pull --no-cache .')
        sh "docker tag ${image.id} registry.devshift.net/${image.id}"
        docker.build('worker-tests', '--no-cache -f Dockerfile.tests .')
    }

    stage('Unit Tests') {
        timeout(10) {
            sh './runtest.sh'
        }
    }

    if (env.BRANCH_NAME == 'master') {
        stage('Push Images') {
            docker.withRegistry('https://push.registry.devshift.net/', 'devshift-registry') {
                image.push('latest')
                image.push(commitId)
            }
        }
    }

}

if (env.BRANCH_NAME == 'master') {
    node('oc') {

        def dcs = ['bayesian-worker-api', 'bayesian-worker-ingestion', 'bayesian-worker-api-graph-import', 'bayesian-worker-ingestion-graph-import']
        lock('f8a_staging') {

            stage('Deploy - Stage') {
                unstash 'template'
                sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=api -v REPLICAS=4 -v WORKER_RUN_DB_MIGRATIONS=1 -v WORKER_EXCLUDE_QUEUES=GraphImporterTask -f template.yaml | oc --context=rh-idev apply -f -"
                sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=api -v WORKER_INCLUDE_QUEUES=GraphImporterTask -v WORKER_NAME_SUFFIX=-graph-import -f template.yaml | oc --context=rh-idev apply -f -"
                sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=ingestion -v WORKER_EXCLUDE_QUEUES=GraphImporterTask -f template.yaml | oc --context=rh-idev apply -f -"
                sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=ingestion -v WORKER_INCLUDE_QUEUES=GraphImporterTask -v WORKER_NAME_SUFFIX=-graph-import -f template.yaml | oc --context=rh-idev apply -f -"
            }

            stage('End-to-End Tests') {
                def result
                try {
                    timeout(20) {
                        sleep 5
                        sh "oc logs -f dc/${dcs[0]}"
                        def e2e = build job: 'fabric8-analytics-common-master', wait: true, propagate: false, parameters: [booleanParam(name: 'runOnOpenShift', value: true)]
                        result = e2e.result
                    }
                } catch (err) {
                    error "Error: ${err}"
                } finally {
                    if (!result?.equals('SUCCESS')) {
                        for (int i=0; i < dcs.size(); i++) {
                            sh "oc rollback ${dcs[i]}"
                        }
                        error 'End-to-End tests failed.'
                    } else {
                        echo 'End-to-End tests passed.'
                    }
                }
            }
        }
    }
}

