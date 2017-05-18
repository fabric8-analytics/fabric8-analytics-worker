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
        sh "docker tag ${image.id} docker-registry.usersys.redhat.com/${image.id}"
        docker.build('f8a-lib-tests', '-f Dockerfile.tests .')
    }

    stage('Tests') {
        timeout(30) {
            sh './runtest.sh'
        }
    }

    stage('Integration Tests') {
        ws {
            docker.withRegistry('https://docker-registry.usersys.redhat.com/') {
                docker.image('bayesian/bayesian-api').pull()
                docker.image('bayesian/coreapi-jobs').pull()
                docker.image('bayesian/coreapi-pgbouncer').pull()
                docker.image('bayesian/coreapi-downstream-data-import').pull()
            }

            git url: 'https://github.com/fabric8-analytics/fabric8-analytics-common.git', branch: 'master'
            dir('integration-tests') {
                timeout(30) {
                    sh './runtest.sh'
                }
            }
        }
    }

    if (env.BRANCH_NAME == 'master') {
        stage('Push Images') {
            docker.withRegistry('https://docker-registry.usersys.redhat.com/') {
                image.push('latest')
                image.push(commitId)
            }
            docker.withRegistry('https://registry.devshift.net/') {
                image.push('latest')
                image.push(commitId)
            }
        }
    }
}

if (env.BRANCH_NAME == 'master') {
    node('oc') {
        stage('Deploy - dev') {
            unstash 'template'
            sh "oc --context=dev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=ingestion -f template.yaml | oc --context=dev apply -f -"
            sh "oc --context=dev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=api -f template.yaml | oc --context=dev apply -f -"
        }

        //stage('Deploy - rh-idev') {
        //    unstash 'template'
        //    sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=ingestion -f template.yaml | oc --context=rh-idev apply -f -"
        //    sh "oc --context=rh-idev process -v IMAGE_TAG=${commitId} -v WORKER_ADMINISTRATION_REGION=api -f template.yaml | oc --context=rh-idev apply -f -"
        //}
    }
}
