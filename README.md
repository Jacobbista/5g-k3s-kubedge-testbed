# 5G K3s KubeEdge Testbed

A comprehensive 5G testbed for research and testing, featuring cloud-edge distribution with K3s, KubeEdge, and Open5GS. This testbed provides a complete 5G infrastructure simulation suitable for edge computing research, MEC applications, and network function testing.

## What you get

- **K3s cluster** (1 master/control-plane, 1 worker, 1 edge)
- **KubeEdge** (CloudCore on worker, EdgeCore on edge) for cloud↔edge orchestration
- **Overlay data-plane** with OVS bridges and VXLAN tunnels between worker↔edge
- **Multus CNI** with NetworkAttachmentDefinitions for 5G interfaces (N1/N2/N3/N4/N6e/N6c)
- **Open5GS-based 5G Core** (NRF/AMF/SMF/UPF/UDM/UDR/PCF/BSF/NSSF/AUSF)
- **UERANSIM** (gNB/UE simulator) and MEC applications
- **Complete automation** with Vagrant + Ansible for reproducible deployments

## Topology (at a glance)

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Master Node   │    │   Worker Node   │    │    Edge Node    │
│  (control-plane)│    │ (datacenter)    │    │     (edge)      │
│ • K3s Server    │    │ • K3s Agent     │    │ • K3s Agent     │
│                 │    │ • CloudCore     │    │ • EdgeCore      │
│                 │    │ • OVS + Multus  │    │ • OVS + Multus  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                 VXLAN tunnels (N1/N2/N3/N4/N6) between worker and edge
```

## Prerequisites

- Vagrant ≥ 2.3.0
- VirtualBox ≥ 6.1.0
- Host OS: Linux/macOS/Windows with virtualization enabled

## Quick start

```bash
git clone <repository-url>
cd 5g-k8s-testbed-vagrant-ansible-fullautodeploy
vagrant up
```

Vagrant provisions 4 VMs: `master`, `worker`, `edge`, `ansible`. The Ansible VM drives all phases via the main playbook.

## Phased deployment

Phases are orchestrated by `ansible/phases/00-main-playbook.yml`:

1. Infrastructure
2. Kubernetes (K3s)
3. KubeEdge
4. Overlay Network (OVS + Multus + NADs)
5. 5G Core (Open5GS)
6. UERANSIM & MEC

Run everything:

```bash
vagrant up  # triggers phases/00-main-playbook.yml on the Ansible VM
```

Run specific phases:

```bash
vagrant ssh ansible
cd /home/vagrant/ansible-ro
ansible-playbook phases/00-main-playbook.yml --tags phase4,phase5 -i inventory.ini
```

> **Note:**  
> When manually running phases with `ansible-playbook`, be sure to specify the inventory file (e.g., `-i inventory.ini`) from the `ansible-ro` directory.

## 5G Network Interfaces

The testbed implements the following 5G interfaces using Multus CNI:

| Interface | Network    | IP Range      | Purpose              | Protocol       |
| --------- | ---------- | ------------- | -------------------- | -------------- |
| **N1**    | n1-net     | 10.201.0.0/24 | UE ↔ AMF (NAS)       | NAS over SCTP  |
| **N2**    | n2-net     | 10.202.0.0/24 | gNB ↔ AMF (NGAP)     | NGAP over SCTP |
| **N3**    | n3-net     | 10.203.0.0/24 | gNB/UE ↔ UPF (GTP-U) | GTP-U over UDP |
| **N4**    | n4-net     | 10.204.0.0/24 | SMF ↔ UPF (PFCP)     | PFCP over UDP  |
| **N6e**   | n6-mec-net | 10.206.0.0/24 | UPF-edge ↔ MEC       | IP routing     |
| **N6c**   | n6-cld-net | 10.207.0.0/24 | UPF-cloud ↔ DN       | IP routing     |

**Static IP assignments:**

- AMF: 10.201.0.100 (N1), 10.202.0.100 (N2)
- SMF: 10.204.0.100 (N4)
- UPF-edge: 10.203.0.100 (N3), 10.204.0.101 (N4)
- UPF-cloud: 10.203.0.101 (N3), 10.204.0.102 (N4)

VXLAN tunnels connect worker↔edge with keys: N1=1, N2=2, N3=3, N4=4, N6e=6, N6c=7.

## Validate

See detailed validation steps in `docs/handbook.md`. Quick checks:

```bash
# Nodes and system pods
kubectl get nodes -o wide
kubectl get pods -A

# Multus NADs
kubectl get network-attachment-definitions -A

# 5G core
kubectl -n 5g get deploy,svc
```

## Research & Testing Focus

This testbed is designed for **5G research and testing** with emphasis on:

- **Edge Computing**: Cloud↔edge distribution with KubeEdge
- **MEC Applications**: Multi-access Edge Computing scenarios
- **Network Function Testing**: Complete 5G Core with realistic interfaces
- **Migration Scenarios**: Dynamic UPF/MEC movement between cloud and edge
- **Performance Analysis**: Ready for monitoring and benchmark tools

## Documentation

- **Complete handbook**: `docs/handbook.md` - Comprehensive guide with all procedures
- **Diagnostic runbooks**: `docs/runbooks/` - Focused troubleshooting procedures
- **Ansible phases**: `ansible/phases/*` - Automated deployment scripts

## Testing & Validation

Use the included test script to validate the phased structure:

```bash
# Validate complete structure
./test-phases.sh validate

# List all available phases
./test-phases.sh list

# Inspect a specific phase
./test-phases.sh 01-infrastructure
./test-phases.sh 02-kubernetes

# Show help
./test-phases.sh help
```

## Troubleshooting

```bash
# K3s
journalctl -u k3s -f
journalctl -u k3s-agent -f

# KubeEdge
kubectl -n kubeedge get pods
kubectl -n kubeedge logs -l app=cloudcore --tail=100

# OVS state
sudo ovs-vsctl show
```

> **Note:** The commands are just examples. You may need to adapt paths and commands to your specific setup and environment. Generally all the cluster related commands are meant to be runned in the **master** node.

## Future Enhancements

- [ ] **Monitoring Stack**: Prometheus/Grafana integration for metrics collection
- [ ] **Benchmark Tools**: Automated performance testing and analysis
- [ ] **Test Suite**: Comprehensive testing framework for different scenarios
- [ ] **Metrics Dashboard**: Real-time visualization of 5G network performance

## License

MIT License. See `LICENSE`.

## Acknowledgements

- K3s (`https://k3s.io`)
- KubeEdge (`https://kubeedge.io`)
- Multus CNI (`https://github.com/k8snetworkplumbingwg/multus-cni`)
- Open5GS (`https://open5gs.org`)
- UERANSIM (`https://github.com/aligungr/UERANSIM`)
