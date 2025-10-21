## Phase 5 — 5G Core Network Functions

### Overview

This phase deploys a complete Open5GS-based 5G Core Network with cloud-edge distribution:

- **Control Plane NFs** (worker node): NRF, AMF, SMF, PCF, BSF, UDM, UDR, NSSF, AUSF
- **User Plane Functions**: UPF-Cloud (worker) + UPF-Edge (edge node)
- **Database**: MongoDB for subscriber data and NF state

All Network Functions leverage the Multus overlay network (Phase 4) for 5G interfaces (N1-N6).

### Theoretical Background

#### 5G Core Architecture (Service-Based Architecture)

The 5G Core uses a Service-Based Architecture (SBA) where Network Functions expose services via HTTP/2 REST APIs:

```
           ┌─────────────────────────────────────────┐
           │         Service Communication           │
           │  (NRF, SBI between NFs via HTTP/2)      │
           └─────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
    ┌───▼────┐         ┌──────▼─────┐      ┌───────▼────┐
    │  AMF   │◄───────►│    SMF     │◄────►│    UPF     │
    │ (N1/N2)│         │   (N4/N7)  │      │ (N3/N6/N9) │
    └────────┘         └────────────┘      └────────────┘
        │                     │                     │
     gNB/UE          Policy/Charging         Data Network
```

**Key Network Functions**:

| NF   | Full Name                        | Purpose                                                      |
| ---- | -------------------------------- | ------------------------------------------------------------ |
| NRF  | Network Repository Function      | Service discovery registry for all NFs                       |
| AMF  | Access & Mobility Management     | Mobility management, authentication, connection to RAN (N2)  |
| SMF  | Session Management Function      | PDU session management, UPF selection, IP address allocation |
| UPF  | User Plane Function              | Packet forwarding, QoS enforcement, traffic routing (N3/N6)  |
| UDM  | Unified Data Management          | Subscriber authentication data                               |
| UDR  | Unified Data Repository          | Subscription data storage                                    |
| PCF  | Policy Control Function          | Policy rules for QoS, charging                               |
| BSF  | Binding Support Function         | Maintains binding information for PCF                        |
| NSSF | Network Slice Selection Function | Network slice selection                                      |
| AUSF | Authentication Server Function   | Authentication for UE                                        |

#### 5G Interfaces

| Interface | Protocol  | Endpoints    | Purpose                                    |
| --------- | --------- | ------------ | ------------------------------------------ |
| **N1**    | NAS/SCTP  | UE ↔ AMF     | Non-Access Stratum signaling               |
| **N2**    | NGAP/SCTP | gNB ↔ AMF    | Control plane between RAN and Core         |
| **N3**    | GTP-U/UDP | gNB/UE ↔ UPF | User plane data tunneling                  |
| **N4**    | PFCP/UDP  | SMF ↔ UPF    | Control plane for UPF (session rules)      |
| **N6**    | IP        | UPF ↔ DN     | Data Network (Internet/MEC) connectivity   |
| **SBI**   | HTTP/2    | NF ↔ NF      | Service-Based Interface (NF communication) |

### Implementation Flow

#### 1. Infrastructure Setup (`infrastructure_setup` role)

- Creates `hostpath` StorageClass for persistent volumes
- Configures `crictl` on worker (k3s containerd) and edge (standalone containerd)
- Pre-pulls container images to speed up deployments

**Key fix**: Edge node uses `unix:///run/containerd/containerd.sock`, not k3s socket.

#### 2. ConfigMaps Setup (`configmaps_setup` role)

- Creates ConfigMaps for each NF configuration (`configs/*.yaml`)
- Creates ConfigMap for init scripts (`scripts/*_init.sh`)
- Uses `kubernetes.core.k8s` API (no shell commands)

#### 3. Network Functions Deployment (`nf_deployments` role)

Uses **template-based approach** for maintainability:

```
templates/
├── mongodb-deployment.yaml.j2     # Database
├── mongodb-service.yaml.j2
├── nf-deployment.yaml.j2          # Generic NF template
└── nf-service.yaml.j2             # Generic Service template
```

**Deployment order**:

1. MongoDB (database must be ready first)
2. NRF (service discovery for other NFs)
3. All other NFs in parallel (they discover each other via NRF)

**Network attachments**: NFs requiring 5G interfaces (AMF, SMF, UPF) use Multus annotations:

```yaml
annotations:
  k8s.v1.cni.cncf.io/networks: |
    [{"name":"n2-net","interface":"n2","ips":["10.202.0.100/24"]}]
```

#### 4. Subscriber Import (`subscriber_import` role)

- Runs a Kubernetes Job to import subscriber data into MongoDB
- Uses Python + pymongo for idempotent subscriber upserts
- Job name includes checksum for idempotency

#### 5. Validation (`validation` role)

- Uses `kubernetes.core.k8s_info` with retries (no shell commands)
- Waits for all Deployments to report `availableReplicas >= 1`
- Validates minimum pod count across all NFs

### Cloud-Edge Distribution

| Component     | Location | Reason                                           |
| ------------- | -------- | ------------------------------------------------ |
| Control Plane | Worker   | Centralized management, service discovery (NRF)  |
| UPF-Cloud     | Worker   | Handles cloud-based data traffic (N6-cloud → DN) |
| UPF-Edge      | Edge     | Low-latency MEC traffic (N6-edge → MEC apps)     |
| MongoDB       | Worker   | Centralized database for all NFs                 |

**Overlay tunnels** (VXLAN from Phase 4) connect worker ↔ edge for N3/N4 interfaces.

### Expected Results

After Phase 5:

```bash
# All NF pods running
kubectl get pods -n 5g
# NAME                         READY   STATUS    RESTARTS   AGE
# mongodb-xxx                  1/1     Running   0          5m
# nrf-xxx                      1/1     Running   0          5m
# amf-xxx                      1/1     Running   0          5m
# smf-xxx                      1/1     Running   0          5m
# upf-cloud-xxx                1/1     Running   0          5m
# upf-edge-xxx                 1/1     Running   0          5m
# udm-xxx                      1/1     Running   0          5m
# udr-xxx                      1/1     Running   0          5m
# pcf-xxx                      1/1     Running   0          5m
# bsf-xxx                      1/1     Running   0          5m
# nssf-xxx                     1/1     Running   0          5m
# ausf-xxx                     1/1     Running   0          5m

# Services exposed
kubectl get svc -n 5g
# NAME         TYPE        CLUSTER-IP      PORT(S)
# mongodb      ClusterIP   10.43.x.x       3000,27017
# nrf          ClusterIP   10.43.x.x       7777,9090
# amf          ClusterIP   10.43.x.x       7777,38412,9090
# ...

# Verify secondary interfaces on AMF (example)
kubectl exec -n 5g amf-xxx -- ip addr show n1
kubectl exec -n 5g amf-xxx -- ip addr show n2
```

### Architecture Highlights

1. **Template-based manifests**: Clean, maintainable, DRY principle
2. **API-driven**: All operations use `kubernetes.core.k8s` (no shell/kubectl)
3. **Idempotent**: Can be re-run safely without state conflicts
4. **Modular roles**: Clear separation (infra → config → deploy → validate)
5. **Cloud-edge aware**: UPF placement optimized for latency

### Troubleshooting Checklist

| Check               | Expected                                               |
| ------------------- | ------------------------------------------------------ |
| **MongoDB ready**   | `kubectl get deploy/mongodb -n 5g` shows 1/1 available |
| **NRF reachable**   | Other NFs log successful NRF registration              |
| **Secondary IPs**   | AMF has N1/N2 IPs, SMF has N4 IP, UPFs have N3/N4/N6   |
| **VXLAN tunnels**   | OVS bridges on worker/edge show active VXLAN ports     |
| **Subscriber data** | `kubectl logs -n 5g job/sub-import-xxx` shows import   |

### Common Issues

**Issue**: UPF-Edge pod fails to start  
**Cause**: Edge node CNI not initialized or secondary interface missing  
**Fix**: Verify Phase 4 Multus edge pod is Running, check `/etc/cni/net.d/00-edge.conflist`

**Issue**: NFs fail to register with NRF  
**Cause**: MongoDB not ready or NRF not started first  
**Fix**: Check MongoDB readiness probe, ensure NRF deployment completes before other NFs

**Issue**: PFCP (N4) session establishment fails  
**Cause**: SMF or UPF cannot reach each other on N4 network  
**Fix**: Verify N4 VXLAN tunnel (`ovs-vsctl show`), check N4 IP assignments on SMF/UPF pods

### Next Phase

Phase 6 deploys UERANSIM (gNB + UE) to test the 5G Core with simulated RAN traffic.

## Future Improvements

Potential enhancements not included in this refactoring:

- [ ] Helm chart conversion (if needed for production)
- [ ] Health check endpoints (liveness/readiness probes for all NFs)
- [ ] Resource limits/requests tuning
- [ ] HPA (Horizontal Pod Autoscaling) for control-plane NFs
- [ ] NetworkPolicies for inter-NF traffic segmentation
- [ ] Prometheus ServiceMonitors for metrics collection
