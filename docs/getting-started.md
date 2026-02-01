# Getting Started

This guide will get you from zero to a running 5G testbed in under 30 minutes.

## Prerequisites

- **Vagrant** >= 2.3.0
- **VirtualBox** >= 6.1.0
- **Host resources**: 16GB RAM, 4+ CPU cores recommended
- **OS**: Linux, macOS, or Windows with virtualization enabled

## Quick Start

### Deploy 5G Core Only (Default)

```bash
git clone https://github.com/Jacobbista/5g-k3s-kubedge-testbed.git
cd 5g-k3s-kubedge-testbed
vagrant up
```

This deploys:
- K3s cluster (master, worker, edge nodes)
- KubeEdge (CloudCore + EdgeCore)
- OVS overlay networks with VXLAN tunnels
- Open5GS 5G Core (AMF, SMF, UPF, NRF, etc.)

### Deploy Full Stack (with UERANSIM)

```bash
DEPLOY_MODE=full vagrant up
```

Adds UERANSIM simulator (gNB + UEs) for end-to-end testing.

## What Gets Deployed

```
+------------------+     +------------------+     +------------------+
|   MASTER NODE    |     |   WORKER NODE    |     |    EDGE NODE     |
|  192.168.56.10   |     |  192.168.56.11   |     |  192.168.56.12   |
|                  |     |                  |     |                  |
|  - K3s Server    |     |  - K3s Agent     |     |  - K3s Agent     |
|  - CloudCore     |     |  - 5G Core NFs   |     |  - EdgeCore      |
|                  |     |  - MongoDB       |     |  - gNB (UERANSIM)|
|                  |     |  - UPF-Cloud     |     |  - UEs (UERANSIM)|
+------------------+     +------------------+     +------------------+
                               |                        |
                               +--- VXLAN Tunnels ------+
                                   (N2, N3, N4, N6)
```

## Verify Deployment

### Check Nodes

```bash
vagrant ssh master
kubectl get nodes
```

Expected output:
```
NAME     STATUS   ROLES                  AGE   VERSION
master   Ready    control-plane,master   10m   v1.30.6+k3s1
worker   Ready    <none>                 8m    v1.30.6+k3s1
edge     Ready    agent,edge             6m    v1.30.6+k3s1
```

### Check 5G Core

```bash
kubectl get pods -n 5g
```

All pods should be `Running`.

### Check UERANSIM (if deployed with full mode)

```bash
kubectl get pods -n 5g -l app=gnb-1
kubectl get pods -n 5g -l app=ue
```

## Access the Cluster

### From Host Machine

```bash
# Copy kubeconfig
vagrant ssh master -c "cat /home/vagrant/kubeconfig" > kubeconfig
export KUBECONFIG=$(pwd)/kubeconfig
kubectl get nodes
```

### From Ansible VM

```bash
vagrant ssh ansible
cd ~/ansible-ro
kubectl --kubeconfig=/home/vagrant/kubeconfig get nodes
```

## Deploy UERANSIM Manually

If you deployed with `core_only` mode (default) and want to add UERANSIM later:

```bash
vagrant ssh ansible
cd ~/ansible-ro
ansible-playbook phases/06-ueransim-mec/playbook.yml -i inventory.ini
```

## Next Steps

- [Architecture Overview](architecture/overview.md) - Understand system design
- [Network Topology](architecture/network-topology.md) - Learn about 5G interfaces
- [Deployment Phases](deployment/phases.md) - Detailed phase documentation
- [Troubleshooting](operations/troubleshooting.md) - Common issues and solutions

## Cleanup

```bash
# Destroy all VMs
vagrant destroy -f

# Or just stop them
vagrant halt
```
