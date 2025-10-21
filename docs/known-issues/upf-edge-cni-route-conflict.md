# Known Issue: UPF-Edge CNI Route Conflict on Edge Node

**Status**: OPEN - Workaround applied  
**Date**: 2025-10-20  
**Impact**: UPF-Edge pods cannot start on edge node (ContainerCreating forever)  
**Workaround**: UPF-Edge deployment scaled to 0 replicas

---

## Problem Description

When attempting to deploy `upf-edge` pods on the edge node (managed by KubeEdge EdgeCore), the pods remain stuck in `ContainerCreating` state with the following error:

```
failed to add route '{0.0.0.0 00000000000000000000ffff00000000} via 10.244.0.1 dev eth0': file exists
```

### Root Cause Analysis

1. **Primary CNI Configuration**: Phase 4 creates `/etc/cni/net.d/10-edge.conflist` on the edge node to provide a primary CNI (required by EdgeCore):

   ```json
   {
     "cniVersion": "1.0.0",
     "name": "edge-cni",
     "plugins": [
       {
         "type": "bridge",
         "bridge": "cni0",
         "isGateway": true,
         "isDefaultGateway": true,
         "ipMasq": true,
         "hairpinMode": true,
         "ipam": {
           "type": "host-local",
           "subnet": "10.244.0.0/24",
           "routes": [{ "dst": "0.0.0.0/0" }]
         }
       },
       {
         "type": "portmap",
         "capabilities": { "portMappings": true }
       }
     ]
   }
   ```

2. **Bridge CNI Plugin Behavior**: The `bridge` plugin creates a `cni0` bridge and attempts to:

   - Assign IP `10.244.0.1` to the bridge (as gateway)
   - Add a default route `0.0.0.0/0 via 10.244.0.1 dev eth0` inside the pod network namespace

3. **Route Conflict**: The CNI plugin fails because:

   - The `cni0` bridge is created but **without IPv4 address** (only IPv6 link-local)
   - The plugin tries to add a route via `10.244.0.1` which doesn't exist as a valid next-hop
   - The kernel reports "file exists" error (route conflict or invalid gateway)

4. **Persistence**: Even after:

   - Deleting the `cni0` bridge manually (`ip link del cni0`)
   - Force-deleting pods
   - Rebooting the edge node

   The bridge is recreated by EdgeCore/containerd on pod creation attempts, and the error recurs.

### Why UPF-Cloud Works but UPF-Edge Doesn't

- **Worker node** (k3s): Uses Flannel as primary CNI, which handles Pod IPs via VXLAN tunnels. Multus adds secondary interfaces (N3, N4, N6) cleanly.
- **Edge node** (EdgeCore): Requires a primary CNI config. The `10-edge.conflist` we created uses the `bridge` plugin, which conflicts with the routing expectations when Multus adds secondary interfaces to `upf-edge` pods.

---

## Current Workaround

UPF-Edge is **permanently disabled** in the Ansible playbook by setting `replicas: 0` in:

```
ansible/phases/05-5g-core/roles/nf_deployments/defaults/main.yml
```

```yaml
# UPF Edge (User Plane Function - Edge)
# DISABLED: CNI route conflict on edge node - see docs/known-issues/upf-edge-cni-route-conflict.md
- name: upf-edge
  replicas: 0 # ← Set to 0 to disable
  node: edge
```

This ensures UPF-Edge remains disabled across playbook re-runs. For testing purposes, only `upf-cloud` on the worker node is used.

---

## Impact on Testbed Functionality

✅ **Works**:

- All control-plane NFs (NRF, AMF, SMF, PCF, UDM, UDR, BSF, NSSF, AUSF)
- UPF-Cloud (worker node) with N3/N4/N6-cloud interfaces
- MongoDB subscriber database
- Multus, Whereabouts, OVS bridges on both worker and edge

❌ **Broken**:

- UPF-Edge (edge node) - cannot start pods
- MEC applications on edge (depend on UPF-Edge for N6-MEC connectivity)

---

## Investigation Required

### Option 1: Use Different Primary CNI on Edge

Replace `/etc/cni/net.d/10-edge.conflist` with a simpler CNI that doesn't manage routing:

```json
{
  "cniVersion": "1.0.0",
  "name": "edge-cni",
  "plugins": [
    {
      "type": "loopback"
    }
  ]
}
```

**Risk**: EdgeCore might require a "real" network CNI, not just loopback.

### Option 2: Fix Bridge Plugin Configuration

Investigate why `cni0` bridge doesn't get the IPv4 address `10.244.0.1`:

- Check EdgeCore/containerd CNI plugin invocation
- Verify IPAM allocation for `host-local`
- Check if EdgeCore overrides CNI plugin behavior

### Option 3: Use Flannel on Edge Node

Deploy a minimal Flannel DaemonSet on the edge node (similar to worker):

- Requires modifying Phase 4 to install Flannel CNI config on edge
- May conflict with KubeEdge's expectations for standalone containerd

### Option 4: Disable Primary CNI Default Route

Modify `10-edge.conflist` to remove the default route requirement:

```json
"routes": []  // Remove default route
```

**Risk**: Pods might not have default routing to external networks.

---

## Relevant Files

- `ansible/phases/04-overlay-network/roles/multus_install/tasks/main.yml` (lines 206-239)
  - Creates `/etc/cni/net.d/10-edge.conflist` on edge node
- `ansible/phases/03-kubeedge/roles/edge_containerd/tasks/main.yml`
  - Installs standalone containerd on edge
- `ansible/phases/03-kubeedge/roles/kubeedge_edgecore/tasks/main.yml`
  - Joins edge to cluster via EdgeCore

---

## Testing Plan (When Investigating MEC)

1. **Test loopback-only CNI**: Replace `10-edge.conflist` with loopback plugin
2. **Test route removal**: Remove `routes` from IPAM config
3. **Check EdgeCore logs**: Monitor `/var/log/kubeedge/edgecore.log` during pod creation
4. **Inspect containerd CNI calls**: Use `crictl` to see how containerd invokes CNI plugins
5. **Compare with k3s**: Analyze how k3s manages primary CNI vs. EdgeCore

---

## References

- KubeEdge EdgeCore CNI requirements: https://kubeedge.io/docs/advanced/cni/
- Multus CNI documentation: https://github.com/k8snetworkplumbingwg/multus-cni
- Bridge CNI plugin spec: https://www.cni.dev/plugins/current/main/bridge/

---

**Action Items**:

- [ ] Research EdgeCore CNI requirements for primary network config
- [ ] Test alternative primary CNI configurations (loopback, macvlan, etc.)
- [ ] Verify if EdgeCore can work without a default route in primary CNI
- [ ] Document MEC testing workflow that requires UPF-Edge

**Priority**: MEDIUM (blocks MEC development, but core 5G functionality works with UPF-Cloud)
