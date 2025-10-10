#!/bin/bash
set -e

echo "[NRF][init] Starting NRF initialization..."

# Wait for MongoDB to be ready
echo "[NRF][init] Waiting for MongoDB..."
# Prefer DNS resolution first to rely on Service discovery
for i in $(seq 30); do
    if getent hosts mongodb >/dev/null 2>&1; then break; fi
    sleep 1
done
while ! nc -z mongodb 27017 && ! nc -z mongodb.5g.svc.cluster.local 27017; do
    echo "[NRF][init] Still waiting for MongoDB..."
    sleep 2
done

echo "[NRF][init] MongoDB is ready, starting NRF daemon..."
# Ensure log directory exists to avoid Open5GS log file open errors
mkdir -p /open5gs/install/var/log/open5gs || true
touch /open5gs/install/var/log/open5gs/nrf.log || true
/open5gs/install/bin/open5gs-nrfd -c ${NRF_CONFIG:-/etc/open5gs/nrf.yaml}
rc=$?
if [ $rc -ne 0 ]; then
  echo "[NRF][init] Daemon exited with code $rc"
  if [ "${DEBUG_HOLD_ON_FAIL:-false}" = "true" ]; then
    echo "[NRF][init] Holding container for debug (DEBUG_HOLD_ON_FAIL=true)"
    sleep infinity
  else
    exit $rc
  fi
fi
