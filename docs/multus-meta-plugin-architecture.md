# Multus CNI Meta-Plugin Architecture

## Overview

This testbed implements Multus CNI as a **meta-plugin** rather than a primary CNI. This architectural choice ensures:

- ✅ Pods without Multus annotations work seamlessly (use only primary CNI)
- ✅ Flannel (worker) and edge-cni (edge) remain the primary CNIs
- ✅ Multus provides secondary interfaces only when explicitly requested

## Architecture Diagram

```
Pod Creation Flow:
─────────────────
1. kubelet/EdgeCore creates pod
2. Calls CNI with config: 00-multus.conflist
3. Multus reads config and sees "delegates": [flannel/edge-cni]
4. Multus calls primary CNI (flannel/edge-cni)
5. Primary CNI creates eth0 interface
6. IF pod has k8s.v1.cni.cncf.io/networks annotation:
   → Multus creates additional interfaces via NADs
7. ELSE:
   → Multus does nothing more (pod has only eth0)
```

## Configuration Files

### Worker Node

**Primary CNI** (`/var/lib/rancher/k3s/agent/etc/cni/net.d/10-flannel.conflist`):

```json
{
  "cniVersion": "1.0.0",
  "name": "cbr0",
  "plugins": [
    {"type": "flannel", "delegate": {...}},
    {"type": "portmap", ...},
    {"type": "bandwidth", ...}
  ]
}
```

**Multus Wrapper** (`/var/lib/rancher/k3s/agent/etc/cni/net.d/00-multus.conflist`):

```json
{
  "cniVersion": "1.0.0",
  "name": "multus-cni-network",
  "plugins": [{
    "type": "multus",
    "kubeconfig": "/var/lib/rancher/k3s/agent/etc/cni/net.d/multus.d/multus.kubeconfig",
    "delegates": [
      {
        "cniVersion": "1.0.0",
        "name": "cbr0",
        "plugins": [
          {"type": "flannel", "delegate": {...}},
          {"type": "portmap", ...},
          {"type": "bandwidth", ...}
        ]
      }
    ]
  }]
}
```

**Key Points**:

- `00-multus.conflist` is loaded first (lexical order)
- Contains the entire `10-flannel.conflist` in the `delegates` array
- Multus calls Flannel for every pod, then adds secondary interfaces if requested

### Edge Node

**Primary CNI** (`/etc/cni/net.d/10-edge.conflist`):

```json
{
  "cniVersion": "1.0.0",
  "name": "edge-cni",
  "plugins": [
    {"type": "bridge", "bridge": "cni0", ...},
    {"type": "portmap", ...}
  ]
}
```

**Multus Wrapper** (`/etc/cni/net.d/00-multus.conflist`):

```json
{
  "cniVersion": "1.0.0",
  "name": "multus-cni-network",
  "plugins": [{
    "type": "multus",
    "kubeconfig": "/etc/cni/net.d/multus.d/multus.kubeconfig",
    "delegates": [
      {
        "cniVersion": "1.0.0",
        "name": "edge-cni",
        "plugins": [
          {"type": "bridge", "bridge": "cni0", ...},
          {"type": "portmap", ...}
        ]
      }
    ]
  }]
}
```

## DaemonSet Configuration

### Critical Parameters

```yaml
args:
  - "--multus-conf-file=auto" # Auto-discover and wrap primary CNI
  - "--multus-log-level=verbose"
  - "--multus-kubeconfig-file-host=/var/lib/rancher/k3s/agent/etc/cni/net.d/multus.d/multus.kubeconfig" # HOST PATH!
  - "--cni-version=1.0.0"
  - "--multus-log-to-stderr=true"
  - "--multus-log-file=/var/log/multus.log"
  - "--skip-multus-binary-copy=false"
```

### Common Mistakes

❌ **Wrong**: Using container mount path for kubeconfig

```yaml
- "--multus-kubeconfig-file-host=/host/etc/cni/net.d/multus.d/multus.kubeconfig"
```

The CNI binary runs on the **host**, not in the container. `/host` doesn't exist on the host filesystem!

✅ **Correct**: Using actual host filesystem path

```yaml
# Worker
- "--multus-kubeconfig-file-host=/var/lib/rancher/k3s/agent/etc/cni/net.d/multus.d/multus.kubeconfig"

# Edge
- "--multus-kubeconfig-file-host=/etc/cni/net.d/multus.d/multus.kubeconfig"
```

❌ **Wrong**: Using incorrect flag name

```yaml
- "--multus-kubeconfig-file=/some/path" # This flag doesn't exist!
```

✅ **Correct**: Using the correct flag

```yaml
- "--multus-kubeconfig-file-host=/some/path"
```

❌ **Wrong**: Trying to skip config file generation

```yaml
- "--multus-conf-file=skip" # Not a valid value!
- "--multus-conf-file=false" # Not a valid value!
```

✅ **Correct**: Auto-generate (default and recommended)

```yaml
- "--multus-conf-file=auto" # Auto-discover and wrap primary CNI
```

## Usage Examples

### Pod WITHOUT Multus (default behavior)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: test-pod
  namespace: default
spec:
  containers:
    - name: test
      image: busybox:latest
      command: ["sleep", "3600"]
```

**Result**:

- Multus calls Flannel/edge-cni
- Pod gets **only `eth0`** interface
- IP from Flannel CIDR (e.g., `10.42.0.x`)

### Pod WITH Multus (secondary interfaces)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: amf
  namespace: 5g
  annotations:
    k8s.v1.cni.cncf.io/networks: |
      [
        {"name": "n1-net", "namespace": "5g", "interface": "n1", "ips": ["10.201.0.100/24"]},
        {"name": "n2-net", "namespace": "5g", "interface": "n2", "ips": ["10.202.0.100/24"]}
      ]
spec:
  containers:
    - name: amf
      image: open5gs-amf:latest
```

**Result**:

- Multus calls Flannel/edge-cni → creates `eth0`
- Multus reads annotation → creates `n1` and `n2` interfaces via NADs
- Pod has **three interfaces**: `eth0`, `n1`, `n2`

## Verification

### Check Multus Configuration

```bash
# Worker
vagrant ssh worker -c "sudo cat /var/lib/rancher/k3s/agent/etc/cni/net.d/00-multus.conflist | jq '.plugins[0]'"

# Expected output includes:
# {
#   "type": "multus",
#   "kubeconfig": "/var/lib/rancher/k3s/agent/etc/cni/net.d/multus.d/multus.kubeconfig",
#   "delegates": [...]
# }
```

### Check Delegation

```bash
# Worker - should delegate to Flannel
vagrant ssh worker -c "sudo cat /var/lib/rancher/k3s/agent/etc/cni/net.d/00-multus.conflist | jq '.plugins[0].delegates[0].plugins[0].type'"
# Expected: "flannel"

# Edge - should delegate to bridge (edge-cni)
vagrant ssh edge -c "sudo cat /etc/cni/net.d/00-multus.conflist | jq '.plugins[0].delegates[0].plugins[0].type'"
# Expected: "bridge"
```

### Test Pod Creation

```bash
# Create a test pod without Multus annotation
kubectl run test-no-multus --image=busybox:latest --command -- sleep 3600

# Check if it got an IP
kubectl get pod test-no-multus -o wide
# Should show IP from Flannel range (10.42.x.x)

# Clean up
kubectl delete pod test-no-multus
```

## References

- [Multus CNI Documentation](https://github.com/k8snetworkplumbingwg/multus-cni/blob/master/docs/how-to-use.md)
- [Multus Thin Plugin](https://github.com/k8snetworkplumbingwg/multus-cni/blob/master/docs/thin-plugin.md)
- [CNI Specification](https://github.com/containernetworking/cni/blob/master/SPEC.md)
