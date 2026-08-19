#!/usr/bin/env bash
# C10 · Streaming delivery lag. Open the CAMARA stream and, for each pushed
# position, record lag = arrival - payload timestamp, plus the update rate, over a
# long run (>= 10 min). The timestamp is the source fix time, so this is freshness
# (fix -> client), not push latency; see stream_lag.py.
#
#   G6_streaming.sh [duration_s]        # default 600 (10 min)
#
# Flow source: the synthetic-adapter walker (demo-001), so movement is continuous;
# wittra is not the C10 source. Same-host, same-clock intent: run on the cluster
# host and reach the gateway over its NodePort (no Cloudflare). The payload
# timestamp is minted inside a cluster VM, so the run also snapshots the host<->VM
# clock offset as a systematic bound on the lag. Owner: experiments/exposure/README.md.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

DURATION="${1:-600}"
COND="C10_streaming"
RUN_DIR="$(new_run_dir "$COND")"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "$COND" >/dev/null

# Token: camara-api-demo (client_credentials). The secret is read from the host
# secrets file and passed straight to curl; it is never echoed.
SECRET="$(grep '^CAMARA_API_DEMO_SECRET' "$REPO_ROOT/.testbed.secrets" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ')"
[ -n "$SECRET" ] || { log "CAMARA_API_DEMO_SECRET not in .testbed.secrets"; exit 1; }
KC="${KELT_KC_URL:-http://$(node_ip):${KELT_KC_NODEPORT:-31910}/auth}"
REALM="${KELT_KC_REALM:-5g-testbed}"
TOKEN="$(curl -s --max-time 15 \
  -d grant_type=client_credentials -d client_id=camara-api-demo \
  --data-urlencode "client_secret=$SECRET" \
  "$KC/realms/$REALM/protocol/openid-connect/token" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)"
[ -n "$TOKEN" ] || { log "token mint failed (check KELT_KC_URL=$KC / realm $REALM)"; exit 1; }

# Clock: the payload timestamp is stamped by the adapter pod, i.e. by its node VM's
# clock. The VMs discipline that clock with chrony against NTP, so capture chrony's
# residual (how far the VM clock sits from true time) as the systematic bound on the
# lag. A cross-SSH `date` diff would only measure the vagrant-ssh round-trip (~2 s),
# not the offset, so it is deliberately not used. Non-fatal if chrony is absent.
NODE="$(kubectl get pod -n "${KELT_POS_NS:-positioning}" -l app=synthetic-adapter \
  -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null | tr -d '\r')"
[ -n "$NODE" ] || NODE="${KELT_ADAPTER_NODE:-worker}"
{
  echo "# chronyc tracking on node '$NODE' (VM clock that stamps the fix timestamp)"
  echo "# 'System time' / 'RMS offset' bound how far this clock sits from NTP truth,"
  echo "# i.e. the systematic component of lag_ms. The host is NTP-synced too."
  vagrant ssh "$NODE" -c "chronyc tracking" 2>/dev/null | sed '/^\[Testbed\]/d'
} >"$RUN_DIR/clock_sync.txt" 2>/dev/null || true

# WS URL from the deployed gateway (http -> ws), token in the query (WS carries no
# Authorization header). The token is kept out of the log line.
GW="$(gateway_url)"
WS="${GW/http:/ws:}/positions/stream?token=$TOKEN"
log "C10: streaming ${DURATION}s from ${GW}/positions/stream -> $RUN_DIR"
python3 "$EXP_ROOT/exposure/stream_lag.py" "$WS" "$DURATION" "$RUN_DIR/samples_${COND}.csv"
log "done -> $RUN_DIR (samples + summary + provenance + clock_sync)"
