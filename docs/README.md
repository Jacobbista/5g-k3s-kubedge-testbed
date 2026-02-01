# Documentation

## Quick Links

- [Getting Started](getting-started.md) - Deploy the testbed in 30 minutes
- [Architecture Overview](architecture/overview.md) - System design and components
- [Troubleshooting](operations/troubleshooting.md) - Common issues and solutions

---

## Architecture

Understand how the system is built.

| Document | Description |
|----------|-------------|
| [Overview](architecture/overview.md) | System components, node roles, technology stack |
| [Network Topology](architecture/network-topology.md) | OVS bridges, VXLAN tunnels, Multus CNI |
| [5G Interfaces](architecture/5g-interfaces.md) | N1, N2, N3, N4, N6 reference points |

---

## Deployment

Setup and configuration guides.

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Quick deployment guide |
| [Deployment Phases](deployment/phases.md) | Phase 1-6 detailed breakdown |
| [Physical RAN](deployment/physical-ran.md) | Connect real femtocell instead of UERANSIM |

---

## Operations

Day-to-day management and diagnostics.

| Document | Description |
|----------|-------------|
| [Troubleshooting](operations/troubleshooting.md) | Common issues and solutions |
| [Handbook](operations/handbook.md) | Complete operational reference |

### Runbooks

Detailed diagnostic procedures for specific subsystems.

| Runbook | Description |
|---------|-------------|
| [GTP-U Path](runbooks/gtpu-path.md) | N3 user plane diagnostics |
| [NGAP Diagnostics](runbooks/ngap-diagnostics.md) | N2 control plane signaling |
| [PFCP Diagnostics](runbooks/pfcp-diagnostics.md) | N4 SMF-UPF interface |
| [OVS VXLAN Health](runbooks/ovs-vxlan-health.md) | Overlay network diagnostics |
| [Multus NAD IPAM](runbooks/multus-nad-ipam.md) | Network attachment issues |

---

## Development

Contributing and testing.

| Document | Description |
|----------|-------------|
| [Testing Guide](development/testing.md) | Run and write tests |
| [Contributing](development/contributing.md) | How to contribute |

---

## Known Issues

Platform-specific limitations and workarounds.

| Issue | Description |
|-------|-------------|
| [KubeEdge Edge Discovery](known-issues/kubeedge-edge-discovery.md) | Service discovery on edge nodes |
| [KubeEdge Multus Env](known-issues/kubeedge-multus-env-injection.md) | Environment variable injection |
| [UPF Edge CNI Route](known-issues/upf-edge-cni-route-conflict.md) | Routing conflicts |

---

## Additional Resources

### Phase-specific Documentation

Each deployment phase has its own README:

- [Phase 1: Infrastructure](../ansible/phases/01-infrastructure/README.md)
- [Phase 2: Kubernetes](../ansible/phases/02-kubernetes/README.md)
- [Phase 3: KubeEdge](../ansible/phases/03-kubeedge/README.md)
- [Phase 4: Overlay Network](../ansible/phases/04-overlay-network/README.md)
- [Phase 5: 5G Core](../ansible/phases/05-5g-core/README.md)
- [Phase 6: UERANSIM](../ansible/phases/06-ueransim-mec/README.md)

### 5G Core Deep Dive

- [NF Architecture](../ansible/phases/05-5g-core/NF_ARCHITECTURE.md) - Network Functions theory and implementation

### Test Suite

- [Test Framework](../tests/README.md) - Automated testing documentation
