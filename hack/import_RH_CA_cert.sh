#!/usr/bin/bash

# For querying internal Pulp instance

curl -O -k https://engineering.redhat.com/Eng-CA.crt
mv Eng-CA.crt /etc/pki/ca-trust/source/anchors/
curl -O -k https://password.corp.redhat.com/RH-IT-Root-CA.crt
mv RH-IT-Root-CA.crt /etc/pki/ca-trust/source/anchors/
update-ca-trust
