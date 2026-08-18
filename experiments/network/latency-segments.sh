#!/usr/bin/env bash
# Family B of experiments/network/segments.md: the intra-cluster latency legs
# that quantify the virtualisation/orchestration overhead (CNI, VXLAN overlay,
# kube-proxy, NodePort ingress) and the CAMARA pipeline network legs.
#
#   latency-segments.sh [count] [interval_s]
#
# Spawns two ephemeral netshoot pods (one per node), measures each segment, saves
# raw ping/curl output plus a summary CSV, and deletes the pods on exit. All
# targets (pod IPs, ClusterIPs, node IPs, NodePorts) are discovered live — nothing
# hardcoded. Owner: experiments/network/segments.md.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/lib/common.sh"

COUNT="${1:-500}"
IVAL="${2:-0.1}"
NETSHOOT_IMG="${KELT_NETSHOOT_IMAGE:-ghcr.io/nicolaka/netshoot:latest}"  # all.yml: network_setup_image
POS_NS="${KELT_POS_NS:-positioning}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$(new_run_dir "latency_segments" "$STAMP")"
"$EXP_ROOT/provenance.sh" "$RUN_DIR" "latency_segments" >/dev/null
CSV="$RUN_DIR/segments.csv"
echo "segment,from,to,rtt_min_ms,rtt_avg_ms,rtt_max_ms,rtt_mdev_ms" >"$CSV"

POD_W="ns-seg-worker-$STAMP"; POD_W="${POD_W,,}"
POD_M="ns-seg-master-$STAMP"; POD_M="${POD_M,,}"

cleanup() {
  kubectl delete pod "$POD_W" "$POD_M" -n "$POS_NS" --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

spawn() { # spawn <pod> <node>
  kubectl run "$1" -n "$POS_NS" --image="$NETSHOOT_IMG" --restart=Never \
    --overrides="{\"spec\":{\"nodeSelector\":{\"kubernetes.io/hostname\":\"$2\"}}}" \
    --command -- sleep 3600 >/dev/null 2>&1 || true
}
wait_ready() { # wait_ready <pod>
  for _ in $(seq 1 60); do
    [ "$(kubectl get pod "$1" -n "$POS_NS" -o jsonpath='{.status.phase}' 2>/dev/null)" = "Running" ] && return 0
    sleep 2
  done
  return 1
}

log "spawning netshoot pods (worker,master)…"
spawn "$POD_W" worker; spawn "$POD_M" master
wait_ready "$POD_W" || die "netshoot on worker not ready"
wait_ready "$POD_M" || die "netshoot on master not ready"

# discovery
node_ip_of() { kubectl get node "$1" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'; }
pod_ip()  { kubectl get pod -n "$2" -l "$1" -o jsonpath='{.items[0].status.podIP}' 2>/dev/null; }
svc_ip()  { kubectl get svc -n "$2" "$1" -o jsonpath='{.spec.clusterIP}' 2>/dev/null; }
MASTER_IP="$(node_ip_of master)"; WORKER_IP="$(node_ip_of worker)"
ENGINE_IP="$(pod_ip app=positioning-engine "$POS_NS")"
GW_IP="$(pod_ip app.kubernetes.io/name=camara-gateway "$CAMARA_NS")"; : "${GW_IP:=$(pod_ip app=camara-gateway "$CAMARA_NS")}"

# ping-based leg: measure <segment> from <pod> to <ip>
ping_leg() { # ping_leg <segment> <pod> <to-label> <to-ip>
  local seg="$1" pod="$2" tolabel="$3" toip="$4" raw line
  [ -n "$toip" ] || { log "skip $seg (no target)"; return; }
  raw="$RUN_DIR/${seg}.ping.txt"
  kubectl exec -n "$POS_NS" "$pod" -- ping -n -c "$COUNT" -i "$IVAL" "$toip" >"$raw" 2>&1 || true
  line="$(grep -E 'rtt|round-trip' "$raw" | tail -1)"    # rtt min/avg/max/mdev = a/b/c/d ms
  local nums; nums="$(printf '%s' "$line" | sed -n 's#.*= *\([0-9./]*\) ms#\1#p')"
  echo "$seg,$pod,$tolabel,$(echo "$nums" | awk -F/ '{print $1","$2","$3","$4}')" >>"$CSV"
}

log "measuring segments (count=$COUNT interval=${IVAL}s)…"
ping_leg host_baseline        "$POD_W" "master-node:$MASTER_IP"   "$MASTER_IP"
ping_leg pod_same_node        "$POD_W" "engine-pod:$ENGINE_IP"    "$ENGINE_IP"
ping_leg pod_cross_node       "$POD_M" "engine-pod:$ENGINE_IP"    "$ENGINE_IP"
ping_leg pipeline_gateway     "$POD_W" "gateway-pod:$GW_IP"       "$GW_IP"
ping_leg pipeline_engine      "$POD_W" "engine-pod:$ENGINE_IP"    "$ENGINE_IP"

log "segments → $CSV"
column -s, -t "$CSV" >&2 || cat "$CSV" >&2
