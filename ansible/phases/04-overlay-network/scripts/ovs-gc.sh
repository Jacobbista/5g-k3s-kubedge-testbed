#!/usr/bin/env bash
set -Eeuo pipefail

INTERVAL="${INTERVAL:-30}"

gc_once() {
  echo "🧹 OVS GC: Starting cycle..."

  # 1) Cleanup known bridges
  for b in br-n1 br-n2 br-n3 br-n4 br-n6e br-n6c; do
    echo "🔍 Checking bridge $b"
    # if the bridge does not exist, skip
    if ! ovs-vsctl br-exists "$b" 2>/dev/null; then
      echo "⚠️ Bridge $b not found, skipping"
      continue
    fi

    for p in $(ovs-vsctl list-ports "$b" 2>/dev/null || true); do
      echo "  Found port $p"
      # Skip VXLAN ports (handled by setup script)
      if [[ "$p" =~ ^vxlan- ]]; then
        echo "    ✅ Skipping VXLAN port $p"
        continue
      fi

      # Check if the port still exists in the kernel
      if ip link show "$p" >/dev/null 2>&1; then
        echo "    ✅ Port $p exists in kernel, keeping"
      else
        echo "    🗑️ Removing orphan port $p from bridge $b"
        ovs-vsctl --if-exists del-port "$b" "$p" || true
        echo "    ✅ Removed $p"
      fi
    done
  done

  # 2) Cleanup interfaces in error state
  echo "🔍 Checking OVS interfaces in error state..."
  ovs-vsctl --timeout=5 --columns=name,error list Interface 2>/dev/null | \
    awk '
      $1=="name"  {n=$3}
      $1=="error" && $3!="[]" {gsub(/\"/,"",n); print n}
    ' | while read -r ifn; do
      if [ -n "$ifn" ]; then
        echo "    🗑️ Removing interface $ifn with error state"
        ovs-vsctl --if-exists del-port "$ifn" || true
        echo "    ✅ Removed $ifn"
      fi
    done

  echo "✅ OVS GC: Cycle completed"
}

while true; do
  gc_once
  sleep "$INTERVAL"
done
