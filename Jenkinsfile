#!/usr/bin/env groovy

node('docker') {

    def image = docker.image('bayesian/cucos-worker')

    stage('Checkout') {
        checkout scm
    }

    stage('Build') {
        dockerCleanup()
        docker.build(image.id, '--pull --no-cache .')
        sh "docker tag ${image.id} docker-registry.usersys.redhat.com/${image.id}"
        docker.build('cucos-lib-tests', '-f Dockerfile.tests .')
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

            git url: 'https://github.com/baytemp/common.git', branch: 'master', credentialsId: 'baytemp-ci-gh'
            dir('integration-tests') {
                timeout(30) {
                    sh './runtest.sh'
                }
            }
        }
    }

    if (env.BRANCH_NAME == 'master') {
        stage('Push Images') {
            def commitId = sh(returnStdout: true, script: 'git rev-parse --short HEAD').trim()
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
            sh 'oc --context=dev deploy bayesian-worker-api --latest'
            sh 'oc --context=dev deploy bayesian-worker-ingestion --latest'
        }

        stage('Deploy - rh-idev') {
            sh 'oc --context=rh-idev deploy bayesian-worker-api --latest'
            sh 'oc --context=rh-idev deploy bayesian-worker-ingestion --latest'
        }
    }
}
