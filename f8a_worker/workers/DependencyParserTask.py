#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 27 19:22:36 2018

@author: slakkara
"""
from f8a_worker.base import BaseTask

def parser():
        pkg_list=['org.apache.maven.resolver:maven-resolver-transport-wagon:1.0.3',
                  'org.apache.maven:maven-repository-metadata:3.5.0',
                  'org.apache.maven:maven-model-builder:3.2.5',
                  'org.jboss.spec.javax.enterprise.concurrent:jboss-concurrency-api_1.0_spec:1.0.0.Final',
                  'org.hibernate:hibernate-validator:5.4.2.Final',
                  'org.hibernate:hibernate-validator-cdi:5.4.2.Final',
                  'org.jboss.forge.addon:bean-validation:3.8.1.Final',
                  'org.apache.commons:commons-lang3:3.5',
                  'org.jboss.shrinkwrap:shrinkwrap-impl-base:1.2.6',
                  'org.apache.maven:maven-settings:3.2.5',
                  'org.jboss.shrinkwrap:shrinkwrap-api:1.2.6',
                  'org.apache.maven:maven-model-builder:3.5.0',
                  'org.jboss.forge.addon:facets-api:3.8.1.Final',
                  'com.github.mifmif:generex:1.0.1',
                  'org.jboss.forge.addon:ui-impl:3.8.1.Final',
                  'org.jboss.narayana.jts:narayana-jts-idlj:5.3.3.Final',
                  'org.slf4j:slf4j-api:1.7.2',
                  'org.apache.maven:maven-builder-support:3.5.0',
                  'org.infinispan:infinispan-commons:8.2.4.Final',
                  'org.wildfly.swarm:msc:2017.11.0',
                  'org.apache.maven:maven-settings-builder:3.5.0',
                  'org.jboss.forge.roaster:roaster-jdt:2.20.1.Final',
                  'org.jboss.arquillian.config:arquillian-config-impl-base:1.1.12.Final',
                  'io.fabric8:zjsonpatch:0.3.0',
                  'com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.9.4',
                  'commons-lang:commons-lang:2.6',
                  'org.wildfly.swarm:fraction-metadata:2017.11.0',
                  'io.fabric8:kubernetes-api:3.0.8',
                  'javax:javaee-api:7.0',
                  'org.eclipse.sisu:org.eclipse.sisu.inject:0.3.3',
                  'org.yaml:snakeyaml:1.19',
                  'ch.qos.logback:logback-classic:1.1.7']

        return(pkg_list)



class DependencyParserTask(BaseTask):
    
        def execute(self, arguments):
            result = parser()
            return {
                    "result": result
                    }