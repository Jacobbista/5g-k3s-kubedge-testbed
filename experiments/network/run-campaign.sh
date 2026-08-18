#!/usr/bin/env bash
# Run one G2 network campaign (C1/C2/C3) against the LIVE deployment through the
# 5G probe, with reps and provenance, and collect the raw result bundles.
#
#   run-campaign.sh <C1_throughput|C2_latency_idle|C3_latency_load> [reps]
#
# Requirements on the probe/UE host:
#   - the probe server is running (./5g-probe/run-probe.sh), reachable at PROBE_URL
#   - KELT_UE_NS names the UE network namespace to run in (the modem's netns)
#
# C3 only: the probe executor is sequential, so this script saturates the link
# with a background iperf3 in the same netns while the latency plan pings. Set
# KELT_C3_LOAD to ul|dl|both (default both).
#
# Nothing is hardcoded: the target comes from the probe config (UPF_TARGET),
# reps default per campaign, results land under experiments/runs/<campaign>/<ts>/.
# Owner: experiments/README.md.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

CAMPAIGN="${1:?usage: run-campaign.sh <C1_throughput|C2_latency_idle|C3_latency_load> [reps]}"
PLAN_FILE="$EXP_ROOT/network/plans/${CAMPAIGN}.json"
[ -f "$PLAN_FILE" ] || die "unknown campaign: $CAMPAIGN (no $PLAN_FILE)"

# Default reps: throughput 5, latency 3.
case "$CAMPAIGN" in
  C1_*) DEFAULT_REPS=5 ;;
  *)    DEFAULT_REPS=3 ;;
esac
REPS="${2:-$DEFAULT_REPS}"
INTER_REP_PAUSE_S="${KELT_INTER_REP_PAUSE_S:-10}"   # "Separate repetitions in time"
PROBE_DIR="${KELT_PROBE_DIR:-$REPO_ROOT/5g-probe}"
PROBE_URL="${PROBE_URL:-http://127.0.0.1:5000}"
PROBE_PY="${KELT_PROBE_PY:-$PROBE_DIR/venv/bin/python}"
UE_NS="${KELT_UE_NS:?set KELT_UE_NS to the UE network namespace}"
C3_LOAD="${KELT_C3_LOAD:-both}"
# Target defaults to the UPF anchor; override for a 5G transport segment
# (e.g. KELT_TARGET=192.168.6.101 for the Uu radio leg). See network/segments.md.
UPF_TARGET="${KELT_TARGET:-$UPF_TARGET}"

[ -x "$PROBE_PY" ] || die "probe venv python not found: $PROBE_PY"
curl -fsS "$PROBE_URL/api/config" >/dev/null 2>&1 || die "probe not reachable at $PROBE_URL (start ./5g-probe/run-probe.sh)"

# Install (or reuse) the plan template; the API slugifies display_name and hands
# back the real plan slug, so we never guess it.
install_plan() {
  local resp slug
  resp="$(curl -sS -X POST "$PROBE_URL/api/plans" -H 'Content-Type: application/json' --data-binary "@$PLAN_FILE")"
  slug="$(printf '%s' "$resp" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("plan_name",""))' 2>/dev/null || true)"
  if [ -z "$slug" ]; then
    # Already exists (409) or expand quirk: recover the slug by display_name.
    local disp; disp="$(python3 -c 'import sys,json; print(json.load(open(sys.argv[1]))["display_name"])' "$PLAN_FILE")"
    slug="$(curl -sS "$PROBE_URL/api/plans" | python3 -c 'import sys,json;
d=json.load(sys.stdin); import os
name=os.environ["DISP"]
print(next((p.get("name") for p in (d if isinstance(d,list) else d.get("plans",[])) if p.get("display_name")==name), ""))' DISP="$disp" 2>/dev/null || true)"
  fi
  [ -n "$slug" ] || die "could not install/resolve plan slug from $PLAN_FILE (response: $resp)"
  echo "$slug"
}

SLUG="$(DISP="" install_plan)"
log "campaign=$CAMPAIGN plan=$SLUG reps=$REPS ns=$UE_NS target=$UPF_TARGET"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$(new_run_dir "$CAMPAIGN" "$STAMP")"
cp "$PLAN_FILE" "$RUN_DIR/plan.json"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "$CAMPAIGN" >/dev/null

# C3: start a saturating load in the UE netns for the given direction.
start_load() {
  [ "$CAMPAIGN" = "C3_latency_load" ] || return 0
  log "C3 load=$C3_LOAD starting background iperf3 saturation"
  case "$C3_LOAD" in
    ul|both) ip netns exec "$UE_NS" iperf3 -c "$UPF_TARGET" -t 320 -P 4        >/dev/null 2>&1 & echo $! >>"$RUN_DIR/.load_pids" ;;
  esac
  case "$C3_LOAD" in
    dl|both) ip netns exec "$UE_NS" iperf3 -c "$UPF_TARGET" -t 320 -P 4 -R     >/dev/null 2>&1 & echo $! >>"$RUN_DIR/.load_pids" ;;
  esac
  sleep 2
}
stop_load() {
  [ -f "$RUN_DIR/.load_pids" ] || return 0
  while read -r pid; do kill "$pid" 2>/dev/null || true; done <"$RUN_DIR/.load_pids"
  rm -f "$RUN_DIR/.load_pids"
}
trap stop_load EXIT

for rep in $(seq 1 "$REPS"); do
  log "rep $rep/$REPS"
  start_load
  if "$PROBE_PY" "$EXP_ROOT/network/lib/start_plan.py" \
        --plan "$SLUG" --namespace "$UE_NS" --target "$UPF_TARGET" --url "$PROBE_URL"; then
    :
  else
    log "rep $rep reported non-success (recorded, not discarded automatically)"
  fi
  stop_load
  # Collect the newest run bundle the probe just wrote for this plan.
  SRC="$PROBE_DIR/results/plan_runs/$SLUG"
  if [ -d "$SRC" ]; then
    latest="$(ls -1dt "$SRC"/run_* 2>/dev/null | head -1)"
    [ -n "$latest" ] && cp -r "$latest" "$RUN_DIR/rep${rep}_$(basename "$latest")"
  fi
  [ "$rep" -lt "$REPS" ] && sleep "$INTER_REP_PAUSE_S"
done

log "done → $RUN_DIR"
