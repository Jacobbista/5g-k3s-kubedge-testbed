#!/bin/bash

# export IP_ADDR=$(awk 'END{print $1}' /etc/hosts)

sleep 25

exec ./nr-ue -c /mnt/ueransim/ue.yaml -i imsi-001011234567895