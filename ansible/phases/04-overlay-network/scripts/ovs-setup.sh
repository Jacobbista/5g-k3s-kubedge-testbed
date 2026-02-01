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
echo "  RAN_INTERFACE=${RAN_INTERFACE:-}"
echo "  RAN_BRIDGE_MODE=${RAN_BRIDGE_MODE:-disabled}"

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

# ============================================================
# Physical RAN Interface Bridging (Optional)
# ============================================================
# When RAN_BRIDGE_MODE is set, bridge a physical interface to OVS
# for direct femtocell/physical gNB connectivity without NAT/NodePort
#
# Modes:
#   - disabled: No physical RAN bridging (default)
#   - n2_only:  Bridge to N2 network only (control plane)
#   - n3_only:  Bridge to N3 network only (user plane)  
#   - n2_n3:    Bridge to both N2 and N3 (full connectivity)
# ============================================================

bridge_ran_interface() {
  local iface="$1" bridge="$2" tag="${3:-}"
  if ovs-vsctl list-ports "$bridge" | grep -q "^${iface}$"; then
    echo "  -> $iface already on $bridge"
    return 0
  fi
  echo "  -> add-port $bridge $iface (physical RAN)"
  if [[ -n "$tag" ]]; then
    ovs-vsctl --may-exist add-port "$bridge" "$iface" tag="$tag"
  else
    ovs-vsctl --may-exist add-port "$bridge" "$iface"
  fi
  ip link set "$iface" up || true
}

if [[ "${RAN_BRIDGE_MODE:-disabled}" != "disabled" ]] && [[ "$NODE_NAME" == "worker" ]]; then
  RAN_IF="${RAN_INTERFACE:-}"
  
  # Auto-detect RAN interface if not specified
  if [[ -z "$RAN_IF" ]]; then
    # Look for interface on 192.168.57.x subnet (RAN network)
    RAN_IF=$(ip -o addr show | grep '192\.168\.57\.' | awk '{print $2}' | head -1)
    if [[ -z "$RAN_IF" ]]; then
      # Fallback: third interface (enp0s9 or eth2)
      RAN_IF=$(ip link | grep -E '^[0-9]+: (enp0s9|eth2):' | sed 's/.*: \([^:]*\):.*/\1/' | head -1)
    fi
  fi
  
  if [[ -n "$RAN_IF" ]] && ip link show "$RAN_IF" &>/dev/null; then
    echo "🔌 Bridging physical RAN interface: $RAN_IF (mode: ${RAN_BRIDGE_MODE})"
    
    # Remove IP from RAN interface (it will be part of OVS bridge)
    ip addr flush dev "$RAN_IF" 2>/dev/null || true
    
    case "${RAN_BRIDGE_MODE}" in
      n2_only)
        echo "  Mode: N2 only (control plane for NGAP/SCTP)"
        bridge_ran_interface "$RAN_IF" "br-n2"
        ;;
      n3_only)
        echo "  Mode: N3 only (user plane for GTP-U)"
        bridge_ran_interface "$RAN_IF" "br-n3"
        ;;
      n2_n3)
        echo "  Mode: N2+N3 (full connectivity)"
        # For combined mode, we create a dedicated RAN bridge and connect it to both
        create_br "br-ran"
        bridge_ran_interface "$RAN_IF" "br-ran"
        # Create patch ports to connect br-ran to br-n2 and br-n3
        ovs-vsctl --may-exist add-port br-ran patch-ran-n2 -- \
          set interface patch-ran-n2 type=patch options:peer=patch-n2-ran
        ovs-vsctl --may-exist add-port br-n2 patch-n2-ran -- \
          set interface patch-n2-ran type=patch options:peer=patch-ran-n2
        ovs-vsctl --may-exist add-port br-ran patch-ran-n3 -- \
          set interface patch-ran-n3 type=patch options:peer=patch-n3-ran
        ovs-vsctl --may-exist add-port br-n3 patch-n3-ran -- \
          set interface patch-n3-ran type=patch options:peer=patch-ran-n3
        echo "  Created br-ran with patches to br-n2 and br-n3"
        ;;
      *)
        echo "⚠️  Unknown RAN_BRIDGE_MODE: ${RAN_BRIDGE_MODE}, skipping"
        ;;
    esac
    echo "✅ Physical RAN interface bridged"
  else
    echo "⚠️  RAN interface not found or not available (RAN_IF=${RAN_IF:-none})"
  fi
else
  if [[ "${RAN_BRIDGE_MODE:-disabled}" != "disabled" ]]; then
    echo "ℹ️  RAN bridging only available on worker node"
  fi
fi

echo "🔎 OVS interfaces (name/type/ofport):"
ovs-vsctl --columns=name,type,ofport list interface | sed 's/ *\n/\n/g' || true

echo "✅ OVS setup completed"
