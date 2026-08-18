#!/usr/bin/env bash
# Capture per-run provenance from the LIVE deployment into
# <run-dir>/provenance.json. Nothing here is typed by hand: commits come from
# git, image versions from the running pods, the two deployment flags from the
# rendered cluster state.
#
# Usage: provenance.sh <run-dir> [condition-label]
#
# Owner: experiments/README.md.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/common.sh"

RUN_DIR="${1:?usage: provenance.sh <run-dir> [condition]}"
CONDITION="${2:-}"
mkdir -p "$RUN_DIR"
OUT="$RUN_DIR/provenance.json"

log "capturing provenance → $OUT"

KELT_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
KELT_DIRTY="$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null | head -c1 | grep -q . && echo true || echo false)"
DATE_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Image tags of the deployment under measurement, read from the running pods
# (cluster = reality; all.yml only states intent). One image per deployment.
images_json() {
  local ns pairs=""
  for ns in "$CORE_NS" $(echo "$EXPOSURE_NS_RE" | tr '|' ' '); do
    while read -r name img; do
      [ -n "$name" ] || continue
      pairs="$pairs{\"ns\":\"$ns\",\"deploy\":\"$name\",\"image\":\"$img\"},"
    done < <(kubectl get deploy -n "$ns" \
        -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.template.spec.containers[0].image}{"\n"}{end}' 2>/dev/null)
  done
  printf '[%s]' "${pairs%,}"
}

# The two deployment flags that define the measured deployment. Values come from
# the rendered cluster, not from all.yml defaults: physical RAN is "on" if the
# AMF carries its N2 physical-RAN address; northbound is "on" if the gateway is
# deployed. (Owner: all.yml physical_ran_enabled / *_enabled derived from
# NORTHBOUND_ENABLED.)
PHYS_RAN="$(kubectl get svc -n "$CORE_NS" -o name 2>/dev/null | grep -qi 'amf' && echo present || echo absent)"
NORTHBOUND="$(kubectl get deploy -n "$CAMARA_NS" -o name 2>/dev/null | grep -qi gateway && echo enabled || echo disabled)"

cat > "$OUT" <<JSON
{
  "date_utc": "$DATE_UTC",
  "condition": "$CONDITION",
  "kelt_commit": "$KELT_COMMIT",
  "kelt_worktree_dirty": $KELT_DIRTY,
  "deployment_flags": {
    "physical_ran": "$PHYS_RAN",
    "northbound": "$NORTHBOUND"
  },
  "upf_target": "$UPF_TARGET",
  "gateway_url": "$(gateway_url 2>/dev/null || echo unknown)",
  "images": $(images_json)
}
JSON

log "provenance written"
cat "$OUT"
