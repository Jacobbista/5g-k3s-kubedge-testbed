# Architecture Overview

## System Components

The 5G KubeEdge Testbed consists of three primary node types orchestrated by Ansible:

```
+-----------------------------------------------------------------------------+
|                              CLOUD CLUSTER                                   |
|  +-----------------------------------------------------------------------+  |
|  |                         MASTER NODE                                    |  |
|  |  - K3s Server (API Server, etcd, Controller Manager, Scheduler)       |  |
|  |  - CloudCore (KubeEdge control plane)                                 |  |
|  |  - CoreDNS                                                            |  |
|  +-----------------------------------------------------------------------+  |
|                                                                              |
|  +-----------------------------------------------------------------------+  |
|  |                         WORKER NODE                                    |  |
|  |  +---------------------------+  +---------------------------+         |  |
|  |  |      5G Core (Open5GS)    |  |     Supporting Services   |         |  |
|  |  |  NRF, AMF, SMF, UDM, UDR  |  |  MongoDB, UPF-Cloud       |         |  |
|  |  |  AUSF, PCF, BSF, NSSF     |  |                           |         |  |
|  |  +---------------------------+  +---------------------------+         |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
                                    |
                              VXLAN Tunnels
                           (N2, N3, N4 overlays)
                                    |
+-----------------------------------------------------------------------------+
|                               EDGE NODE                                      |
|  +-----------------------------------------------------------------------+  |
|  |  EdgeCore (KubeEdge data plane)                                       |  |
|  +-----------------------------------------------------------------------+  |
|  +-----------------------------------------------------------------------+  |
|  |  UERANSIM (RAN Simulator)                                             |  |
|  |  - gNB: Simulated base station                                        |  |
|  |  - UEs: Simulated user equipment                                      |  |
|  +-----------------------------------------------------------------------+  |
|  +-----------------------------------------------------------------------+  |
|  |  UPF-Edge (optional): Local breakout for MEC                          |  |
|  +-----------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------+
```

## Node Roles

| Node | IP | Role | Key Components |
|------|-----|------|----------------|
| **Master** | 192.168.56.10 | K8s Control Plane | K3s Server, CloudCore, CoreDNS |
| **Worker** | 192.168.56.11 | 5G Core Hosting | Open5GS NFs, MongoDB, UPF-Cloud |
| **Edge** | 192.168.56.12 | RAN & UE | EdgeCore, gNB, UEs, UPF-Edge |
| **Ansible** | 192.168.56.13 | Orchestration | Ansible playbooks, SSH keys |

## Technology Stack

### Kubernetes Layer
- **K3s**: Lightweight Kubernetes distribution
- **KubeEdge**: Extends Kubernetes to edge nodes
- **Multus CNI**: Multiple network interfaces per pod

### Network Layer
- **OVS (Open vSwitch)**: Software-defined networking
- **VXLAN**: Overlay tunnels between worker and edge
- **Whereabouts**: IPAM for dynamic IP allocation

### 5G Layer
- **Open5GS**: 5G Core Network Functions
- **UERANSIM**: 5G RAN and UE simulator
- **MongoDB**: Subscriber database

## Communication Flows

### Control Plane

```
UE --[RRC]--> gNB --[NGAP/N2]--> AMF --[SBI]--> NRF/SMF/AUSF/UDM
```

### User Plane

```
UE --[NR-Uu]--> gNB --[GTP-U/N3]--> UPF --[N6]--> Data Network
```

### Management Plane

```
Ansible --> SSH --> All Nodes
kubectl --> K8s API --> Master --> Worker/Edge
```

## KubeEdge Architecture

KubeEdge enables Kubernetes workloads on edge nodes with intermittent connectivity:

```
+-------------------+                    +-------------------+
|   CLOUD SIDE      |                    |   EDGE SIDE       |
|                   |                    |                   |
|  +-------------+  |                    |  +-------------+  |
|  | CloudCore   |  |<-- WebSocket -->   |  | EdgeCore    |  |
|  |             |  |    (port 10000)    |  |             |  |
|  | - EdgeHub   |  |                    |  | - EdgeHub   |  |
|  | - DeviceCtl |  |                    |  | - MetaMgr   |  |
|  | - SyncCtl   |  |                    |  | - Edged     |  |
|  +-------------+  |                    |  +-------------+  |
+-------------------+                    +-------------------+
```

### Edge Limitations

Pods on edge nodes face specific challenges:
- No CoreDNS access (no service name resolution)
- ConfigMaps/Secrets may not sync automatically
- ServiceAccount token projection has bugs

**Solution**: Init containers query K8s API directly with long-lived tokens.

## Deployment Phases

| Phase | Description | Duration |
|-------|-------------|----------|
| 1 | Infrastructure (OVS, packages) | ~2 min |
| 2 | Kubernetes (K3s cluster) | ~3 min |
| 3 | KubeEdge (CloudCore + EdgeCore) | ~2 min |
| 4 | Overlay Network (Multus, NADs) | ~3 min |
| 5 | 5G Core (Open5GS NFs) | ~5 min |
| 6 | UERANSIM (gNB, UEs) | ~3 min |

Total: ~18 minutes for full deployment.

## Related Documentation

- [Network Topology](network-topology.md) - OVS bridges, VXLAN tunnels
- [5G Interfaces](5g-interfaces.md) - N1, N2, N3, N4, N6 details
- [Deployment Phases](../deployment/phases.md) - Phase-by-phase guide
