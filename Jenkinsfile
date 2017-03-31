#!/usr/bin/env groovy

node('docker') {

    def workerImage = docker.image('bayesian/cucos-worker')
    def downstreamImage = docker.image('bayesian/coreapi-downstream-data-import')

    stage('Checkout') {
        checkout scm
    }

    stage('Build') {
        dockerCleanup()
        // build worker image
        docker.build(workerImage.id, '--pull --no-cache .')
        sh "docker tag ${workerImage.id} docker-registry.usersys.redhat.com/${workerImage.id}"
        // build downstream-data-import image
        docker.build(downstreamImage.id, '-f Dockerfile.downstream-data-import --pull --no-cache .')
        sh "docker tag ${downstreamImage.id} docker-registry.usersys.redhat.com/${downstreamImage.id}"
        // build test image
        docker.build('cucos-lib-tests', '-f Dockerfile.tests .')
    }

    stage('Tests') {
        timeout(30) {
            sh './runtest.sh'
        }
    }

    //stage('Integration Tests') {
    //    ws {
    //        docker.withRegistry('https://docker-registry.usersys.redhat.com/') {
    //            docker.image('bayesian/bayesian-api').pull()
    //            docker.image('bayesian/coreapi-jobs').pull()
    //            docker.image('bayesian/coreapi-pgbouncer').pull()
    //        }

    //        git url: 'https://github.com/baytemp/common.git', branch: 'master', credentialsId: 'baytemp-ci-gh'
    //        dir('integration-tests') {
    //            timeout(30) {
    //                sh './runtest.sh'
    //            }
    //        }
    //    }
    //}

    if (env.BRANCH_NAME == 'master') {
        stage('Push Images') {
            def commitId = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
            docker.withRegistry('https://docker-registry.usersys.redhat.com/') {
                workerImage.push('latest')
                workerImage.push(commitId)
                downstreamImage.push('latest')
                downstreamImage.push(commitId)
            }
            docker.withRegistry('https://registry.devshift.net/') {
                workerImage.push('latest')
                workerImage.push(commitId)
                downstreamImage.push('latest')
                downstreamImage.push(commitId)
            }
        }
    }
}

if (env.BRANCH_NAME == 'master') {
    node('oc') {
        stage('Deploy - dev') {
            sh 'oc --context=dev deploy bayesian-worker-api --latest'
            sh 'oc --context=dev deploy bayesian-worker-ingestion --latest'
            rerunOpenShiftJob {
                jobName = 'bayesian-downstream-data-import'
                cluster = 'dev'
            }
        }

        stage('Deploy - rh-idev') {
            sh 'oc --context=rh-idev deploy bayesian-worker-api --latest'
            sh 'oc --context=rh-idev deploy bayesian-worker-ingestion --latest'
            rerunOpenShiftJob {
                jobName = 'bayesian-downstream-data-import'
                cluster = 'rh-idev'
            }
        }
    }
}
