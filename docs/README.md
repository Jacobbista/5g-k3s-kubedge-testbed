# Documentation Index

## Getting Started

- [Main README](../README.md) - Project overview and quick start
- [Handbook](handbook.md) - Complete operational handbook

## Phase Documentation

### Phase 1: Infrastructure Setup

- [Phase 1 README](../ansible/phases/01-infrastructure/README.md) - System packages, OVS, network setup

### Phase 2: Kubernetes Cluster

- [Phase 2 README](../ansible/phases/02-kubernetes/README.md) - K3s deployment (master + worker)

### Phase 3: KubeEdge Integration

- [Phase 3 README](../ansible/phases/03-kubeedge/README.md) - CloudCore and EdgeCore setup

### Phase 4: Overlay Network

- [Phase 4 README](../ansible/phases/04-overlay-network/README.md) - Multus, OVS, VXLAN tunnels
- [Multus Meta-Plugin Architecture](multus-meta-plugin-architecture.md) - CNI configuration details

### Phase 5: 5G Core Network

- [Phase 5 README](../ansible/phases/05-5g-core/README.md) - Open5GS deployment
- [NF Architecture](../ansible/phases/05-5g-core/NF_ARCHITECTURE.md) - Network Functions deep dive

### Phase 6: UERANSIM & MEC

- [Phase 6 README](../ansible/phases/06-ueransim-mec/README.md) - gNB, UE, MEC deployment
- [Phase 6 Refactoring](../ansible/phases/06-ueransim-mec/REFACTORING.md) - Implementation details
- [Phase 6 Implementation Guide](phase6-implementation-guide.md) - Deployment procedures
- [Phase 6 Best Practices](phase6-best-practices.md) - Design patterns and recommendations
- [gNB Endpoints Sync](../ansible/phases/06-ueransim-mec/roles/endpoints_sync/README.md) - DNS resolution for Multus IPs

## Operational Guides

### Runbooks

- [Runbooks Index](runbooks/README.md) - Diagnostic procedures overview
- [GTP-U Path Diagnostics](runbooks/gtpu-path.md) - User plane troubleshooting
- [Multus NAD and IPAM](runbooks/multus-nad-ipam.md) - Network attachment diagnostics
- [NGAP Diagnostics](runbooks/ngap-diagnostics.md) - Control plane signaling
- [OVS VXLAN Health](runbooks/ovs-vxlan-health.md) - Overlay network diagnostics
- [PFCP Diagnostics](runbooks/pfcp-diagnostics.md) - SMF-UPF interface troubleshooting

### Known Issues

- [UPF Edge CNI Route Conflict](known-issues/upf-edge-cni-route-conflict.md) - UPF routing issues on edge node

## Testing

- [Test Framework](../tests/README.md) - Automated test suite
- [Test Configuration](../tests/test_config.yaml) - Test parameters

## Architecture

- [Multus Meta-Plugin Architecture](multus-meta-plugin-architecture.md) - CNI configuration deep dive
- [5G Network Functions Architecture](../ansible/phases/05-5g-core/NF_ARCHITECTURE.md) - NF theory and implementation

## Contributing

When adding documentation:

1. Use clear, concise English
2. Include code examples where relevant
3. Add cross-references to related docs
4. Update this index
5. Follow existing structure (README per phase, runbooks for operations)
