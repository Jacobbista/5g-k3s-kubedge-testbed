#!/bin/bash
set -e

echo "[AUSF][init] Starting AUSF initialization..."

# Wait for MongoDB
echo "[AUSF][init] Waiting for MongoDB..."
for i in $(seq 30); do
    if getent hosts mongodb >/dev/null 2>&1; then break; fi
    sleep 1
done
while ! nc -z mongodb 27017 && ! nc -z mongodb.5g.svc.cluster.local 27017; do
    echo "[AUSF][init] Still waiting for MongoDB..."
    sleep 2
done

# Wait for NRF
echo "[AUSF][init] Waiting for NRF SBI..."
for i in $(seq 30); do
    if getent hosts nrf >/dev/null 2>&1; then break; fi
    sleep 1
done
while ! nc -z nrf 7777 && ! nc -z nrf.5g.svc.cluster.local 7777; do
    echo "[AUSF][init] Still waiting for NRF..."
    sleep 2
done

echo "[AUSF][init] Starting AUSF daemon..."
mkdir -p /open5gs/install/var/log/open5gs || true
touch /open5gs/install/var/log/open5gs/ausf.log || true
/open5gs/install/bin/open5gs-ausfd -c ${AUSF_CONFIG:-/etc/open5gs/ausf.yaml}
rc=$?
if [ $rc -ne 0 ]; then
  echo "[AUSF][init] Daemon exited with code $rc"
  if [ "${DEBUG_HOLD_ON_FAIL:-false}" = "true" ]; then
    echo "[AUSF][init] Holding container for debug (DEBUG_HOLD_ON_FAIL=true)"
    sleep infinity
  else
    exit $rc
  fi
fi
