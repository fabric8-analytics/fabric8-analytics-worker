#!/usr/bin/bash -e

# For querying BlackDuck Hub

true | openssl s_client -connect ec2-54-201-40-10.us-west-2.compute.amazonaws.com:8443 2>/dev/null | openssl x509 > /etc/pki/ca-trust/source/BlackDuckHub.crt
keytool -import -noprompt -trustcacerts -alias BlackDuckHub -keystore `echo /opt/blackduck/scan.cli-*`/jre/lib/security/jssecacerts -file /etc/pki/ca-trust/source/BlackDuckHub.crt -storepass BlackDuckHub
