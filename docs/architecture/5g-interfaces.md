# 5G Network Interfaces

## Interface Overview

The testbed implements standard 3GPP 5G interfaces:

```
+-------+                              +-------+
|  UE   |                              |  DN   |
+---+---+                              +---+---+
    |                                      |
    | N1 (NAS)                             | N6
    |                                      |
+---+---+         +-------+         +------+------+
|  gNB  +---------+  AMF  +---------+     UPF     |
+---+---+   N2    +---+---+   N11   +------+------+
    |                 |                    |
    |                 | N8/N12             | N4
    |                 |                    |
    |            +----+----+          +----+----+
    +------------+   SMF   +----------+   PCF   |
         N3      +----+----+          +---------+
                      |
                 +----+----+
                 |   NRF   |
                 +---------+
```

## Interface Details

### N1 - UE to AMF (NAS)

| Property | Value |
|----------|-------|
| **Purpose** | Non-Access Stratum signaling |
| **Protocol** | NAS over SCTP |
| **Subnet** | 10.201.0.0/24 |
| **AMF IP** | 10.201.0.100 |
| **OVS Bridge** | br-n1 |

**Messages**: Registration, Authentication, Security Mode, PDU Session Establishment

### N2 - gNB to AMF (NGAP)

| Property | Value |
|----------|-------|
| **Purpose** | NG Application Protocol |
| **Protocol** | NGAP over SCTP |
| **Port** | 38412 |
| **Subnet** | 10.202.0.0/24 |
| **AMF IP** | 10.202.0.100 |
| **OVS Bridge** | br-n2 |

**Messages**: NG Setup, Initial UE Message, PDU Session Resource Setup

```bash
# Verify AMF NGAP port
kubectl exec -n 5g deploy/amf -- ss -Slnp | grep 38412
```

### N3 - gNB to UPF (GTP-U)

| Property | Value |
|----------|-------|
| **Purpose** | User plane data transport |
| **Protocol** | GTP-U over UDP |
| **Port** | 2152 |
| **Subnet** | 10.203.0.0/24 |
| **UPF-Cloud IP** | 10.203.0.101 |
| **UPF-Edge IP** | 10.203.0.100 |
| **OVS Bridge** | br-n3 |

**Traffic**: Encapsulated user data (IP packets in GTP tunnels)

```bash
# Verify UPF GTP-U port
kubectl exec -n 5g deploy/upf-cloud -- ss -ulnp | grep 2152
```

### N4 - SMF to UPF (PFCP)

| Property | Value |
|----------|-------|
| **Purpose** | Packet Forwarding Control Protocol |
| **Protocol** | PFCP over UDP |
| **Port** | 8805 |
| **Subnet** | 10.204.0.0/24 |
| **SMF IP** | 10.204.0.100 |
| **UPF-Cloud IP** | 10.204.0.102 |
| **UPF-Edge IP** | 10.204.0.101 |
| **OVS Bridge** | br-n4 |

**Messages**: Session Establishment, Modification, Deletion

```bash
# Verify SMF PFCP port
kubectl exec -n 5g deploy/smf -- ss -ulnp | grep 8805
```

### N6 - UPF to Data Network

| Property | Value |
|----------|-------|
| **Purpose** | Connection to external networks |
| **Protocol** | IP routing |
| **Edge Subnet** | 10.206.0.0/24 (MEC) |
| **Cloud Subnet** | 10.207.0.0/24 (Internet) |
| **OVS Bridge** | br-n6e, br-n6c |

### SBI - Service Based Interface

| Property | Value |
|----------|-------|
| **Purpose** | Inter-NF communication |
| **Protocol** | HTTP/2 (no TLS in testbed) |
| **Discovery** | NRF-based |
| **Network** | ClusterIP Services |

**NFs using SBI**: NRF, AMF, SMF, UDM, UDR, AUSF, PCF, BSF, NSSF

## Static IP Assignments

| Component | N1 | N2 | N3 | N4 |
|-----------|-----|-----|-----|-----|
| AMF | 10.201.0.100 | 10.202.0.100 | - | - |
| SMF | - | - | - | 10.204.0.100 |
| UPF-Cloud | - | - | 10.203.0.101 | 10.204.0.102 |
| UPF-Edge | - | - | 10.203.0.100 | 10.204.0.101 |

## Per-Cell Network Configuration

For multi-cell deployments, each cell gets dedicated N2/N3 networks:

| Cell | N2 Subnet | N3 Subnet | AMF N2 IP |
|------|-----------|-----------|-----------|
| Cell 1 | 10.202.1.0/24 | 10.203.1.0/24 | 10.202.1.10 |
| Cell 2 | 10.202.2.0/24 | 10.203.2.0/24 | 10.202.2.10 |

## Verification Commands

### Check Interface IPs

```bash
# AMF interfaces
kubectl exec -n 5g deploy/amf -- ip -o -4 addr show | grep -E 'n1|n2'

# UPF interfaces
kubectl exec -n 5g deploy/upf-cloud -- ip -o -4 addr show | grep -E 'n3|n4'
```

### Check Network Status Annotation

```bash
kubectl get pod -n 5g -l app=amf -o jsonpath='{.items[0].metadata.annotations.k8s\.v1\.cni\.cncf\.io/network-status}' | jq .
```

### Verify Connectivity

```bash
# From gNB to AMF (N2)
kubectl exec -n 5g deploy/gnb-1 -- ping -c 3 10.202.0.100

# From gNB to UPF (N3)
kubectl exec -n 5g deploy/gnb-1 -- ping -c 3 10.203.0.101
```

## Related Documentation

- [Network Topology](network-topology.md) - OVS and VXLAN configuration
- [NGAP Diagnostics](../runbooks/ngap-diagnostics.md) - N2 troubleshooting
- [PFCP Diagnostics](../runbooks/pfcp-diagnostics.md) - N4 troubleshooting
- [GTP-U Path](../runbooks/gtpu-path.md) - N3 troubleshooting
