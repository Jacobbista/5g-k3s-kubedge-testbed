# Known Issue: KubeEdge Injects Empty KUBERNETES_SERVICE_* Env Vars

**Status**: RESOLVED - Workaround implemented  
**Date**: 2026-01-31  
**Impact**: Multus pods on edge nodes fail with CrashLoopBackOff  
**Resolution**: Use static Multus conflist instead of auto mode on edge

---

## Problem Description

When deploying Multus DaemonSet on KubeEdge-managed edge nodes, the pods enter `CrashLoopBackOff` with kubeconfig generation errors.

### Symptoms

```
# Pod status
multus-edge-xxxxx   0/1     CrashLoopBackOff   6 (30s ago)

# Pod logs
failed to create multus kubeconfig: ...
```

Or the kubeconfig is generated with an invalid server address:

```yaml
# Generated kubeconfig on edge (BROKEN)
server: https://[]:     # Empty host and port!
```

### Root Cause

KubeEdge EdgeCore **injects environment variables** into all containers running on edge nodes. These include:

```
KUBERNETES_SERVICE_HOST=       # Empty!
KUBERNETES_SERVICE_PORT=       # Empty!
```

When the pod spec also defines these variables:

```yaml
env:
  - name: KUBERNETES_SERVICE_HOST
    value: "192.168.56.10"
  - name: KUBERNETES_SERVICE_PORT
    value: "6443"
```

The container runtime ends up with **duplicate entries**:

```
KUBERNETES_SERVICE_HOST=192.168.56.10   # From pod spec
KUBERNETES_SERVICE_PORT=6443            # From pod spec
KUBERNETES_SERVICE_HOST=                # Injected by KubeEdge (wins)
KUBERNETES_SERVICE_PORT=                # Injected by KubeEdge (wins)
```

The **last value wins**, so the Multus `thin_entrypoint` reads empty strings and generates an invalid kubeconfig.

### Verification

SSH into edge node and inspect container environment:

```bash
# Find the Multus container
sudo ctr -n k8s.io containers list | grep multus

# Check env vars (replace CONTAINER_ID)
sudo ctr -n k8s.io containers info CONTAINER_ID | grep -E 'KUBERNETES|SERVICE'
```

Output showing the duplicate injection:

```
"KUBERNETES_SERVICE_HOST=192.168.56.10",   # Our value
"KUBERNETES_SERVICE_PORT=6443",             # Our value  
"KUBERNETES_SERVICE_HOST=",                 # KubeEdge injection (empty!)
"KUBERNETES_SERVICE_PORT="                  # KubeEdge injection (empty!)
```

---

## Resolution

Use **static config mode** for Multus on edge nodes instead of auto mode.

### How It Works

1. **Worker node (k3s)**: Uses `--multus-conf-file=auto` which:
   - Reads existing CNI configs
   - Generates kubeconfig from env vars (works because no KubeEdge injection)

2. **Edge node (KubeEdge)**: Uses `--multus-conf-file=/path/to/config` which:
   - Uses pre-generated conflist from template
   - Kubeconfig path is `/var/lib/multus/multus.kubeconfig` (outside CNI dir)
   - This prevents thin_entrypoint from attempting to regenerate the kubeconfig

### Implementation

**Kubeconfig location**: `/var/lib/multus/multus.kubeconfig`
- Created by Ansible before DaemonSet deployment
- Path is **outside** `/host/etc/cni/net.d` to prevent thin_entrypoint from detecting and overwriting it
- Mounted into the container as read-only volume

**Template**: `ansible/phases/04-overlay-network/roles/multus_install/templates/00-multus-edge.conflist.j2`

```json
{
  "cniVersion": "1.0.0",
  "name": "multus-cni-network",
  "plugins": [{
    "type": "multus",
    "kubeconfig": "/var/lib/multus/multus.kubeconfig",
    "delegates": [...]
  }]
}
```

**DaemonSet (edge)**: Uses static config with external kubeconfig

```yaml
args:
  - "--multus-conf-file=/host/etc/cni/net.d/00-multus.conflist"
  # NOT auto mode
volumeMounts:
  - name: multus-kubeconfig
    mountPath: /var/lib/multus
    readOnly: true
volumes:
  - name: multus-kubeconfig
    hostPath:
      path: /var/lib/multus
```

**DaemonSet (worker)**: Uses auto mode (works fine)

```yaml
args:
  - "--multus-conf-file=auto"
  - "--multus-kubeconfig-file-host=/var/lib/.../multus.d/multus.kubeconfig"
```

---

## Affected Files

- `ansible/phases/04-overlay-network/roles/multus_install/tasks/main.yml`
  - Lines 432-445: Static conflist creation for edge
  - Lines 571-646: Edge DaemonSet with static config mode
- `ansible/phases/04-overlay-network/roles/multus_install/templates/00-multus-edge.conflist.j2`
  - Static Multus configuration for edge

---

## Why Not Just Make Kubeconfig Immutable?

Initial attempt was to use `chattr +i` to prevent thin_entrypoint from overwriting our kubeconfig.

**Problem**: thin_entrypoint crashes when it can't write:

```
failed to create multus kubeconfig: cannot replace "...": operation not permitted
```

The static config approach is cleaner because:
1. No filesystem tricks needed
2. thin_entrypoint works normally (just skips kubeconfig generation)
3. Easy to understand and maintain

---

## References

- Multus thin_entrypoint source: https://github.com/k8snetworkplumbingwg/multus-cni/blob/master/images/entrypoint.sh
- KubeEdge environment injection: EdgeCore injects service discovery env vars for compatibility with standard Kubernetes pods
- CNI config loading order: Files sorted alphabetically, `00-multus.conflist` takes precedence

---

**Testing**: Re-run phase 4 playbook and verify both worker and edge Multus pods are Running:

```bash
vagrant ssh ansible -c "cd ~/ansible-work && ansible-playbook phases/04-overlay-network/playbook.yml -i inventory.ini"
vagrant ssh master -c "sudo k3s kubectl get pods -n kube-system -l app=multus -o wide"
```
