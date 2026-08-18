#!/usr/bin/env bash
# C8 · Resource footprint (G2). Snapshot per-pod CPU and memory from Prometheus
# for a 5-minute window, core network (namespace 5g) separated from the exposure
# stack (positioning|camara|mec). Run once per condition AFTER that condition has
# been active for at least the window length.
#
#   C8_footprint.sh <condition-label>     # idle | throughput | request-load
#
# cAdvisor is scraped by the phase-07 Prometheus (via the API-server proxy), so
# container_cpu_usage_seconds_total / container_memory_working_set_bytes are
# available per pod. Verify the label names on your cluster once (namespace/pod/
# container) — the API-server proxy path can rename them.
#
# Owner: experiments/README.md (G2 footprint).

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

CONDITION="${1:?usage: C8_footprint.sh <idle|throughput|request-load>}"
WINDOW="${KELT_FOOTPRINT_WINDOW:-5m}"

prom_url() {
  if [ -n "${KELT_PROM_URL:-}" ]; then echo "$KELT_PROM_URL"; return; fi
  local svc="${KELT_PROM_SVC:-prometheus}"
  echo "http://$(node_ip):$(svc_nodeport "$MONITORING_NS" "$svc")"
}
PROM="$(prom_url)"
curl -fsS "$PROM/-/ready" >/dev/null 2>&1 || curl -fsS "$PROM/api/v1/status/config" >/dev/null 2>&1 \
  || die "Prometheus not reachable at $PROM (set KELT_PROM_URL)"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$(new_run_dir "C8_footprint" "$STAMP")"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "C8/$CONDITION" >/dev/null
OUT="$RUN_DIR/footprint_${CONDITION}.csv"

# Run an instant PromQL query, emit "value|label=... " rows.
q() { curl -fsS --get "$PROM/api/v1/query" --data-urlencode "query=$1"; }

emit_layer() { # emit_layer <layer> <ns-selector>
  local layer="$1" nssel="$2" sel
  sel="namespace=~\"$nssel\",container!=\"\",container!=\"POD\""
  # CPU cores over the window (mean via rate); memory mean and peak (working set).
  q "sum by (namespace,pod) (rate(container_cpu_usage_seconds_total{$sel}[$WINDOW]))" \
    | python3 "$EXP_ROOT/footprint/_promcsv.py" "$layer" cpu_cores >>"$OUT"
  q "sum by (namespace,pod) (avg_over_time(container_memory_working_set_bytes{$sel}[$WINDOW]))" \
    | python3 "$EXP_ROOT/footprint/_promcsv.py" "$layer" mem_bytes_mean >>"$OUT"
  q "sum by (namespace,pod) (max_over_time(container_memory_working_set_bytes{$sel}[$WINDOW]))" \
    | python3 "$EXP_ROOT/footprint/_promcsv.py" "$layer" mem_bytes_peak >>"$OUT"
}

echo "layer,namespace,pod,metric,value" >"$OUT"
emit_layer core "$CORE_NS"
emit_layer exposure "$EXPOSURE_NS_RE"

log "footprint ($CONDITION) → $OUT"
column -s, -t "$OUT" >&2 || cat "$OUT" >&2
