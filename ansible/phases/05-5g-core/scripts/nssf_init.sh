#!/bin/bash
set -e

echo "[NSSF][init] Starting NSSF initialization..."

# Wait for MongoDB
echo "[NSSF][init] Waiting for MongoDB..."
for i in $(seq 30); do
    if getent hosts mongodb >/dev/null 2>&1; then break; fi
    sleep 1
done
while ! nc -z mongodb 27017 && ! nc -z mongodb.5g.svc.cluster.local 27017; do
    echo "[NSSF][init] Still waiting for MongoDB..."
    sleep 2
done

# Wait for NRF
echo "[NSSF][init] Waiting for NRF SBI..."
for i in $(seq 30); do
    if getent hosts nrf >/dev/null 2>&1; then break; fi
    sleep 1
done
while ! nc -z nrf 7777 && ! nc -z nrf.5g.svc.cluster.local 7777; do
    echo "[NSSF][init] Still waiting for NRF..."
    sleep 2
done

echo "[NSSF][init] Starting NSSF daemon..."
mkdir -p /open5gs/install/var/log/open5gs || true
touch /open5gs/install/var/log/open5gs/nssf.log || true
exec /open5gs/install/bin/open5gs-nssfd -c ${NSSF_CONFIG:-/etc/open5gs/nssf.yaml}
