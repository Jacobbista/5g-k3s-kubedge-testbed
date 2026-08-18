#!/usr/bin/env bash
# G6 · Where the response time goes. Drive N requests at a fixed rate against the
# deployed CAMARA gateway for one condition and record, per request, the
# end-to-end time AND the x-correlator the gateway coins. The per-hop stage split
# is NOT reconstructed here: northbound instruments each hop (receive/emit ts +
# x-correlator) and KELT aggregates those logs by x-correlator (role split agreed
# G6). Until that instrumentation ships, this records end-to-end + the correlator
# join key and snapshots the pod logs for later aggregation.
#
#   G6_latency.sh <fresh|hit|local> [count] [rate_per_s]
#
# Conditions (agreed with northbound):
#   fresh   maxAge=0 in the body → bypass cache → measures the real pipeline
#           (for a wittra asset this includes the WAN; subtract the adapter→vendor
#            span from the per-hop trace to get the WAN-free number — no mock deploy)
#   hit     served from cache → ~0, a separate trivial number
#   local   a local-source asset (wifi/mock) → pipeline with no external call
# A deterministic WAN-free repro is a LOCAL `make demo` concern (vendor-adapter
# repointed at the schema-driven mock-vendor via WITTRA_BASE_URL), NOT a cluster
# component. 1000 requests at ~5/s by default.
#
# Set the condition in the request body (asset + maxAge); the driver does not
# invent the contract. Confirm path/body from the profiled OpenAPI
# ("$(gateway_url)"/docs). Owner: experiments/exposure/README.md.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

COND="${1:?usage: G6_latency.sh <fresh|hit|local> [count] [rate]}"
COUNT="${2:-1000}"
RATE="${3:-5}"
GW="$(gateway_url)"
TOKEN="${KELT_CAMARA_TOKEN:?set KELT_CAMARA_TOKEN to a valid CAMARA access token (do not commit it)}"
RETRIEVE_PATH="${KELT_RETRIEVE_PATH:-/location-retrieval/v3/retrieve}"  # confirm via /docs
BODY_FILE="${KELT_RETRIEVE_BODY:?set KELT_RETRIEVE_BODY to a JSON body (asset + maxAge for this condition)}"

[ -f "$BODY_FILE" ] || die "retrieve body file not found: $BODY_FILE"
command -v curl >/dev/null || die "curl required"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$(new_run_dir "G6_latency" "$STAMP")"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "G6/$COND" >/dev/null
CSV="$RUN_DIR/requests_${COND}.csv"
echo "i,http_status,x_correlator,time_total_s,time_starttransfer_s" >"$CSV"
HDR="$(mktemp)"; trap 'rm -f "$HDR"' EXIT

log "G6 $COND: $COUNT requests at ${RATE}/s → $GW$RETRIEVE_PATH"
SLEEP="$(python3 -c "print(1.0/float($RATE))")"
for i in $(seq 1 "$COUNT"); do
  read -r status ttot tstart < <(curl -s -o /dev/null -D "$HDR" \
      -w '%{http_code} %{time_total} %{time_starttransfer}\n' \
      -X POST "$GW$RETRIEVE_PATH" \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      --data-binary "@$BODY_FILE")
  xcorr="$(grep -i '^x-correlator:' "$HDR" | tail -1 | tr -d '\r' | awk '{print $2}')"
  echo "$i,$status,${xcorr:-},$ttot,$tstart" >>"$CSV"
  sleep "$SLEEP"
done

# Per-hop aggregation is KELT's job, keyed by x-correlator, once northbound ships
# the per-hop instrumentation (their next work item). Snapshot the pod logs for
# the run window so the aggregation can run later; the x-correlator column above
# is the join key. Gateway + engine now; add the adapter pod for the wittra path.
for spec in "$CAMARA_NS:deploy/${KELT_CAMARA_SVC:-camara-gateway}:gateway" \
            "${KELT_POS_NS:-positioning}:deploy/positioning-engine:engine"; do
  ns="${spec%%:*}"; rest="${spec#*:}"; obj="${rest%:*}"; tag="${rest##*:}"
  kubectl logs -n "$ns" "$obj" --since=1h >"$RUN_DIR/hoplog_${tag}_${COND}.txt" 2>/dev/null || true
done
log "done → $RUN_DIR (end-to-end + x-correlator in $CSV; per-hop split pends northbound instrumentation — see README)"
