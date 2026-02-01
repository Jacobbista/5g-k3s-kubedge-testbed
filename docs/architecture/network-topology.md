# Network Topology

## Overview

The testbed uses multiple isolated overlay networks to simulate 5G reference points. Each network is implemented as an OVS bridge with VXLAN tunnels connecting worker and edge nodes.

## Physical Network

```
+------------------+     +------------------+     +------------------+
|   MASTER NODE    |     |   WORKER NODE    |     |    EDGE NODE     |
|  192.168.56.10   |     |  192.168.56.11   |     |  192.168.56.12   |
+--------+---------+     +--------+---------+     +--------+---------+
         |                        |                        |
         +------------------------+------------------------+
                          |
                   Management Network
                   192.168.56.0/24
```

## Overlay Networks

Each 5G interface has its own isolated overlay network:

```
+------------------+                              +------------------+
|   WORKER NODE    |                              |    EDGE NODE     |
|                  |                              |                  |
|  +------------+  |         VXLAN VNI 102        |  +------------+  |
|  |   br-n2    |  |<---------------------------->|  |   br-n2    |  |
|  | 10.202.x.x |  |                              |  | 10.202.x.x |  |
|  +------------+  |                              |  +------------+  |
|                  |                              |                  |
|  +------------+  |         VXLAN VNI 103        |  +------------+  |
|  |   br-n3    |  |<---------------------------->|  |   br-n3    |  |
|  | 10.203.x.x |  |                              |  | 10.203.x.x |  |
|  +------------+  |                              |  +------------+  |
|                  |                              |                  |
|  +------------+  |         VXLAN VNI 104        |  +------------+  |
|  |   br-n4    |  |<---------------------------->|  |   br-n4    |  |
|  | 10.204.x.x |  |                              |  | 10.204.x.x |  |
|  +------------+  |                              |  +------------+  |
+------------------+                              +------------------+
```

## OVS Bridge Configuration

### Bridges per Node

| Bridge | VNI | Subnet | Purpose |
|--------|-----|--------|---------|
| br-n1 | 101 | 10.201.0.0/24 | N1 (NAS signaling) |
| br-n2 | 102 | 10.202.0.0/24 | N2 (NGAP control) |
| br-n3 | 103 | 10.203.0.0/24 | N3 (GTP-U data) |
| br-n4 | 104 | 10.204.0.0/24 | N4 (PFCP control) |
| br-n6e | 106 | 10.206.0.0/24 | N6 edge (MEC) |
| br-n6c | 106 | 10.207.0.0/24 | N6 cloud (DN) |

### Per-Cell Networks

For multi-cell deployments, additional bridges are created:

| Bridge | VNI | Subnet | Purpose |
|--------|-----|--------|---------|
| br-n2-cell-1 | 1021 | 10.202.1.0/24 | Cell 1 N2 |
| br-n3-cell-1 | 1031 | 10.203.1.0/24 | Cell 1 N3 |

## Multus CNI Configuration

Pods attach to overlay networks via NetworkAttachmentDefinitions (NADs):

```yaml
apiVersion: k8s.cni.cncf.io/v1
kind: NetworkAttachmentDefinition
metadata:
  name: n2-net
  namespace: 5g
spec:
  config: |
    {
      "cniVersion": "0.3.1",
      "type": "ovs",
      "bridge": "br-n2",
      "ipam": {
        "type": "whereabouts",
        "range": "10.202.0.0/24",
        "range_start": "10.202.0.10",
        "range_end": "10.202.0.250"
      }
    }
```

### Pod Network Annotation

```yaml
metadata:
  annotations:
    k8s.v1.cni.cncf.io/networks: |
      [
        {"name": "n2-net", "interface": "n2"},
        {"name": "n3-net", "interface": "n3"}
      ]
```

## VXLAN Tunnel Details

### Tunnel Endpoints

| Source | Destination | Transport |
|--------|-------------|-----------|
| Worker (192.168.56.11) | Edge (192.168.56.12) | UDP 4789 |

### Tunnel Configuration

```bash
# On worker node
ovs-vsctl add-port br-n2 vxlan-n2 -- \
  set interface vxlan-n2 type=vxlan \
  options:key=102 \
  options:remote_ip=192.168.56.12 \
  options:local_ip=192.168.56.11
```

## Physical RAN Integration

For connecting physical femtocells, a dedicated RAN network is available:

```
+------------------+                    +------------------+
|   WORKER NODE    |                    |    FEMTOCELL     |
|                  |                    |                  |
|  +------------+  |   192.168.57.0/24  |  +------------+  |
|  |   br-ran   |  |<------------------>|  |    gNB     |  |
|  |   (OVS)    |  |                    |  |            |  |
|  +-----+------+  |                    |  +------------+  |
|        |         |                    +------------------+
|  +-----+------+  |
|  |   br-n2    |  |  (patch ports)
|  +------------+  |
|  |   br-n3    |  |
|  +------------+  |
+------------------+
```

See [Physical RAN Integration](../deployment/physical-ran.md) for setup instructions.

## Verification Commands

### Check OVS Bridges

```bash
vagrant ssh worker
sudo ovs-vsctl show
```

### Check VXLAN Tunnels

```bash
sudo ovs-vsctl list interface | grep -A5 vxlan
```

### Check NADs

```bash
kubectl get net-attach-def -A
```

### Check Pod Network Status

```bash
kubectl get pod <pod-name> -n 5g -o jsonpath='{.metadata.annotations.k8s\.v1\.cni\.cncf\.io/network-status}' | jq .
```

## Troubleshooting

### VXLAN Connectivity Issues

```bash
# Test VXLAN port
nc -vzu 192.168.56.12 4789

# Check bridge ports
sudo ovs-vsctl list-ports br-n2
```

### IP Assignment Issues

```bash
# Check Whereabouts IP pool
kubectl get ippools.whereabouts.cni.cncf.io -A
```

See [OVS VXLAN Health Runbook](../runbooks/ovs-vxlan-health.md) for detailed diagnostics.
