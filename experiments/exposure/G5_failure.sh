#!/usr/bin/env bash
# G5 · Source failure. Two recorded behaviours, no new instrumentation:
#   1. stop the vendor endpoint → measure time until the API reports NO position
#      (report nothing rather than a stale fix), observe retry/backoff.
#   2. remove an adapter → the engine drops it after the heartbeat expires and
#      keeps serving the rest without a restart.
#
#   G5_failure.sh vendor <adapter-deploy>     # scale the adapter to 0, poll the API
#   G5_failure.sh adapter <adapter-name>      # delete the adapter, watch the engine drop it
#
# Confirm the CURRENT heartbeat/retry values from the engine code/config, not from
# memory. This script observes; it does not assert the timings.
# Owner: experiments/exposure/README.md.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

MODE="${1:?usage: G5_failure.sh <vendor|adapter> <name>}"
NAME="${2:?adapter deployment/name required}"
POS_NS="${KELT_POS_NS:-positioning}"     # all.yml positioning_namespace
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$(new_run_dir "G5_failure" "$STAMP")"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "G5_failure/$MODE:$NAME" >/dev/null
OBS="$RUN_DIR/observation.log"

stamp() { date -u +%H:%M:%S.%3NZ; }

case "$MODE" in
  vendor)
    log "scaling adapter $NAME to 0 in $POS_NS; polling engine /adapters"
    { echo "$(stamp) STOP vendor: scale $NAME -> 0"
      kubectl scale deploy "$NAME" -n "$POS_NS" --replicas=0
      for _ in $(seq 1 120); do
        echo "$(stamp) $(kubectl exec -n "$POS_NS" deploy/positioning-engine -- \
              python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8080/adapters",timeout=3).read().decode())' 2>/dev/null | head -c 400)"
        sleep 5
      done
    } | tee "$OBS"
    ;;
  adapter)
    log "deleting adapter $NAME; watching the engine drop it after heartbeat TTL"
    { echo "$(stamp) DELETE adapter deployment $NAME"
      kubectl delete deploy "$NAME" -n "$POS_NS" --ignore-not-found
      for _ in $(seq 1 120); do
        echo "$(stamp) $(kubectl exec -n "$POS_NS" deploy/positioning-engine -- \
              python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8080/adapters",timeout=3).read().decode())' 2>/dev/null | head -c 400)"
        sleep 5
      done
    } | tee "$OBS"
    ;;
  *) die "unknown mode: $MODE (vendor|adapter)" ;;
esac

log "observation → $OBS (restore with: kubectl scale/redeploy; or re-run phase 10)"
