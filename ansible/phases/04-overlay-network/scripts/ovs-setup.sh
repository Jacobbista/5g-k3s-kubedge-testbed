#!/usr/bin/env bash
set -Eeuo pipefail

echo "🔧 Configuring kernel/network defaults..."
sysctl -w net.ipv4.ip_forward=1 >/dev/null || true
sysctl -w net.ipv4.conf.all.rp_filter=0 >/dev/null || true
iptables -P FORWARD ACCEPT || true

echo "🔧 Environment:"
echo "  NODE_NAME=${NODE_NAME:-}"
echo "  WORKER_IP=${WORKER_IP:-}"
echo "  EDGE_IP=${EDGE_IP:-}"
echo "  CELL_COUNT=${CELL_COUNT:-0}"

BRIDGES=(br-n1 br-n2 br-n3 br-n4 br-n6e br-n6c)

create_br() {
  local br="$1"
  echo "  -> add-br $br"
  ovs-vsctl --may-exist add-br "$br"
  ip link set "$br" up || true
  ip link set "$br" mtu 1450 || true
}

calc_local_ip() {
  local peer="$1"
  ip -4 route get "$peer" 2>/dev/null \
    | awk '/src/ {for(i=1;i<=NF;i++) if ($i=="src"){print $(i+1); exit}}'
}

create_vx() { # $1=bridge  $2=ifname  $3=vni  $4=remote_ip  $5=local_ip
  local br="$1" ifn="$2" vni="$3" rip="$4" lip="$5"
  create_br "$br"
  echo "  -> add-port $br $ifn (VNI=$vni remote=$rip local=$lip)"
  ovs-vsctl --may-exist add-port "$br" "$ifn" -- \
    set interface "$ifn" type=vxlan \
      options:key="$vni" \
      options:remote_ip="$rip" \
      options:local_ip="$lip" \
      options:dst_port=4789 \
      options:tos=inherit \
      options:df_default=false
}

# Decide VXLAN peer endpoint
if [[ "${NODE_NAME:-}" == "edge" ]]; then
  : "${WORKER_IP:?WORKER_IP required when NODE_NAME=edge}"
  PEER="$WORKER_IP"
elif [[ "${NODE_NAME:-}" == "worker" ]]; then
  : "${EDGE_IP:?EDGE_IP required when NODE_NAME=worker}"
  PEER="$EDGE_IP"
else
  echo "❌ NODE_NAME must be 'edge' or 'worker'"; exit 1
fi

LOCAL_TUN_IP="$(calc_local_ip "$PEER")"
if [[ -z "${LOCAL_TUN_IP:-}" ]]; then
  echo "❌ Cannot determine LOCAL_TUN_IP toward $PEER"; exit 1
fi
echo "🔧 LOCAL_TUN_IP=$LOCAL_TUN_IP  PEER=$PEER"

# Create VXLAN ports for global interfaces
echo "🌐 Creating global network bridges..."
if [[ "$NODE_NAME" == "edge" ]]; then
  create_vx br-n1 vxlan-n1 101 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n2 vxlan-n2 102 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n3 vxlan-n3 103 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n4 vxlan-n4 104 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n6e vxlan-n6 106 "$PEER" "$LOCAL_TUN_IP"
else
  create_vx br-n1 vxlan-n1 101 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n2 vxlan-n2 102 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n3 vxlan-n3 103 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n4 vxlan-n4 104 "$PEER" "$LOCAL_TUN_IP"
  create_vx br-n6c vxlan-n6 106 "$PEER" "$LOCAL_TUN_IP"
fi

# Create per-cell bridges (for N2 and N3 per cell)
if [[ "${CELL_COUNT:-0}" -gt 0 ]]; then
  echo "📱 Creating per-cell network bridges (cells: 1-${CELL_COUNT})..."
  for cell_id in $(seq 1 "$CELL_COUNT"); do
    # N2-cell-{id}: VNI 102{id} (e.g., cell-1 → VNI 1021)
    vni_n2="102${cell_id}"
    create_vx "br-n2-cell-${cell_id}" "vxlan-n2-cell-${cell_id}" "$vni_n2" "$PEER" "$LOCAL_TUN_IP"
    
    # N3-cell-{id}: VNI 103{id} (e.g., cell-1 → VNI 1031)
    vni_n3="103${cell_id}"
    create_vx "br-n3-cell-${cell_id}" "vxlan-n3-cell-${cell_id}" "$vni_n3" "$PEER" "$LOCAL_TUN_IP"
  done
  echo "✅ Created ${CELL_COUNT} cells (N2 + N3 per cell)"
else
  echo "ℹ️  No per-cell bridges (CELL_COUNT=${CELL_COUNT:-0})"
fi

echo "🔎 OVS interfaces (name/type/ofport):"
ovs-vsctl --columns=name,type,ofport list interface | sed 's/ *\n/\n/g' || true

echo "✅ OVS setup completed"
