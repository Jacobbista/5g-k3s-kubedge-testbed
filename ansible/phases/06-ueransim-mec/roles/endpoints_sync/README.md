# gNB Endpoints Sync

## Problem

gNB pods (UERANSIM) have secondary network interfaces via Multus (N2, N3) with IPs different from the pod's primary IP.

When a UE pod tries to connect to the gNB via Kubernetes DNS:

```
gnb-1.5g.svc.cluster.local
```

The Kubernetes Service normally resolves to the **primary IP** (eth0), but UERANSIM communicates via the **N2 interface** with a different IP.

## Current Solution: Two Parallel Mechanisms

### 1. **CronJob: gnb-endpoints-sync** ✅

**What it does**:

- Every minute, reads pods with label `component=gnb`
- Extracts N2 IP from Multus annotations (`k8s.v1.cni.cncf.io/network-status`)
- Creates/updates Kubernetes Endpoints with the real N2 IP

**Result**:

```yaml
apiVersion: v1
kind: Endpoints
metadata:
  name: gnb-1
  namespace: 5g
subsets:
  - addresses:
      - ip: 10.202.1.10 # N2 IP (Multus), not eth0
    ports:
      - port: 38412
        protocol: SCTP
        name: ngap
      - port: 2152
        protocol: UDP
        name: gtpu
```

**Advantages**:

- ✅ Kubernetes DNS works normally: `gnb-1.5g.svc.cluster.local` → `10.202.1.10`
- ✅ Dynamic IP (auto-updates if gNB restarts)
- ✅ Visibility: `kubectl get endpoints gnb-1 -n 5g`

**Limitations**:

- ❌ Requires working CoreDNS
- ❌ **Does NOT work on EdgeCore**: pods on edge node (KubeEdge) don't have access to CoreDNS

### 2. **hostAliases (in UE pod)** 🩹

**What it does**:
Hardcodes the gNB IP in `/etc/hosts` of the UE container:

```yaml
spec:
  hostAliases:
    - ip: "10.202.1.10" # gNB N2 IP
      hostnames:
        - "gnb-1.5g.svc.cluster.local"
```

**Advantages**:

- ✅ Works on **edge node** (EdgeCore) where CoreDNS is unavailable
- ✅ Immediate and guaranteed solution

**Limitations**:

- ❌ **Static** IP hardcoded in manifest
- ❌ If gNB restarts with different IP, UE pod must be recreated
- ❌ Not scalable for dynamic deployments

## Why Do We Need Both?

| Pod Location | CoreDNS? | Mechanism Used               |
| ------------ | -------- | ---------------------------- |
| Worker node  | ✅ Yes   | gnb-endpoints-sync (dynamic) |
| Edge node    | ❌ No    | hostAliases (hardcoded)      |

**In this testbed**: UEs run on **edge node** → `hostAliases` is required.

The `gnb-endpoints-sync` CronJob is maintained for:

1. **Visibility**: `kubectl get endpoints` shows real IPs
2. **Future**: When/if UEs are deployed on worker nodes
3. **Completeness**: Other components might use DNS

## Ideal Solution (TODO)

### Option A: Fix CoreDNS on EdgeCore (RECOMMENDED)

**Configure EdgeCore to use cluster CoreDNS**:

1. Edit `/etc/kubeedge/config/edgecore.yaml`:

```yaml
modules:
  edged:
    clusterDNS: "10.43.0.10" # CoreDNS service ClusterIP
    clusterDomain: "cluster.local"
```

2. Restart EdgeCore:

```bash
systemctl restart edgecore
```

3. **Remove** `hostAliases` from UE template
4. **Keep** only `gnb-endpoints-sync`

**Advantages**:

- ✅ Clean, standard Kubernetes solution
- ✅ Dynamic IPs for all pods
- ✅ Single mechanism to maintain

**Complexity**: Moderate (EdgeCore configuration)

### Option B: Inject IP Dynamically via Init Container

**Instead of hardcoding the IP**, use an init container that:

1. Queries Kubernetes Endpoints: `kubectl get endpoints gnb-1 -o json`
2. Extracts N2 IP
3. Rewrites UERANSIM config with real IP

**Advantages**:

- ✅ Dynamic IP
- ✅ Works without CoreDNS

**Disadvantages**:

- ❌ More complex
- ❌ Init container needs kubectl/permissions

### Option C: Service with externalIPs

**Create Service with externalIPs** pointing to N2 IP:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: gnb-1
spec:
  externalIPs:
    - 10.202.1.10 # N2 IP
  ports:
    - port: 38412
```

**Advantages**:

- ✅ Standard Kubernetes

**Disadvantages**:

- ❌ Static IP in Service manifest
- ❌ Still requires gnb-endpoints-sync to populate externalIPs dynamically

## Current Implementation (Dynamic Discovery)

**✅ IMPLEMENTED: Option B (Init Container)**

UE pods now use dynamic gNB discovery via init container:

1. **gnb-discovery** init container queries Kubernetes Endpoints API
2. Extracts gNB N2 IP from the endpoint
3. Writes IP to shared volume
4. **config-gen** init container reads IP and generates UE config with direct IP

**Advantages**:

- ✅ Fully dynamic - no hardcoded IPs
- ✅ Works on edge nodes without kube-proxy
- ✅ Supports dynamic topology (add/remove gNBs at runtime)
- ✅ When gNB restarts with new IP, just restart UE pod

**Architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│                     gNB Deployment                              │
│  - Gets dynamic IP from whereabouts (e.g., 10.202.1.23)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              gnb-endpoints-sync CronJob (every 1m)              │
│  - Reads gNB pod's Multus network-status annotation             │
│  - Updates Kubernetes Endpoints with N2 IP                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Endpoints                         │
│  gnb-1 → 10.202.1.23 (N2 IP, not eth0)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              UE Pod Init Container (gnb-discovery)              │
│  - Queries: GET /api/v1/namespaces/5g/endpoints/gnb-1           │
│  - Extracts IP: 10.202.1.23                                     │
│  - Writes to: /discovery/gnb-ip                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              UE Pod Init Container (config-gen)                 │
│  - Reads gNB IP from /discovery/gnb-ip                          │
│  - Generates ue-config.yaml with gnbSearchList: [10.202.1.23]   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UE Main Container                            │
│  - Connects directly to gNB N2 IP                               │
│  - No DNS resolution needed                                     │
└─────────────────────────────────────────────────────────────────┘
```

**For Dynamic Topology Management**:

To add a new gNB + UEs at runtime:
1. Create new gNB Deployment + Service (via API/UI)
2. gnb-endpoints-sync will populate the endpoint within 1 minute
3. Create new UE StatefulSet pointing to the new gNB
4. UE init container will discover gNB IP automatically

## Files Involved

- **CronJob**: `roles/endpoints_sync/templates/cronjob.yaml.j2`
- **Python Script**: `roles/endpoints_sync/templates/sync_endpoints.py.j2`
- **RBAC**: `roles/endpoints_sync/templates/rbac.yaml.j2`
- **UE StatefulSet** (hostAliases): `roles/ue_deployment/templates/ue-statefulset.yaml.j2` (line 31-34)

## Testing

```bash
# Verify populated Endpoints
kubectl get endpoints gnb-1 -n 5g -o yaml

# Verify DNS from worker (works)
kubectl run -it --rm debug --image=alpine --restart=Never -- \
  nslookup gnb-1.5g.svc.cluster.local

# Verify /etc/hosts in UE pod (edge node)
kubectl exec -it ue-cell-1-0 -n 5g -- cat /etc/hosts | grep gnb
```

## References

- [KubeEdge EdgeCore DNS](https://kubeedge.io/en/docs/advanced/edgecore/)
- [Multus Network Status Annotations](https://github.com/k8snetworkplumbingwg/multus-cni/blob/master/docs/quickstart.md#network-status)
- [Kubernetes Endpoints](https://kubernetes.io/docs/concepts/services-networking/service/#endpoints)
