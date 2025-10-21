## Phase 1 — Infrastructure Setup

### Overview

Prepares each node for the Kubernetes + overlay networking stack by installing baseline tools, configuring routing, and ensuring connectivity.

This phase ensures the host OS is ready before any container networking layer is introduced.

### Theoretical Background

At this stage we're still outside Kubernetes — configuring the Linux networking substrate that later supports CNI overlays.

- **IP forwarding**: allows nodes to route traffic between interfaces (e.g., between VXLAN and management interfaces)
- **iptables / netfilter**: defines forwarding and NAT rules that emulate Internet connectivity for lab environments
- **Chrony**: synchronizes clocks — important for distributed tracing and time-sensitive network protocols
- **Open vSwitch (OVS)**: installed early on worker and edge nodes to prepare for Phase 4's data-plane overlay

### Implementation Details

| Component                           | Purpose                                                |
| ----------------------------------- | ------------------------------------------------------ |
| `chrony`                            | Provides NTP sync across nodes                         |
| `iptables` + `netfilter-persistent` | Configures forwarding and optional NAT                 |
| `/etc/hosts`                        | Static resolution of all cluster nodes from inventory  |
| `ping` tests                        | Validates layer-3 reachability between all nodes       |
| `openvswitch-switch`                | Installed on worker/edge nodes, but not yet configured |

### Key Variables

- `enable_ovs_on_workers_edges` (bool): install/start OVS on data-plane nodes
- `enable_node_nat` (bool): enable SNAT for outbound connectivity
- `uplink_iface` (str): default uplink interface (auto-detected via Ansible)

### Outputs

- `chrony` and `openvswitch-switch` services running (where applicable)
- `net.ipv4.ip_forward = 1` system-wide
- Persistent iptables rules (if NAT enabled)
- `/etc/hosts` includes all inventory hosts
- Verified node-to-node connectivity

### Notes

- On Ubuntu with the nftables backend, `netfilter-persistent` stores iptables-nft rules
- NAT is optional; disable it (`enable_node_nat: false`) in clusters with upstream routing
