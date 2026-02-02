# Deployment Phases

The testbed is deployed in six sequential phases, each building on the previous.

## Phase Overview

| Phase | Name | Duration | Description |
|-------|------|----------|-------------|
| 1 | Infrastructure | ~2 min | System packages, OVS installation |
| 2 | Kubernetes | ~3 min | K3s cluster setup |
| 3 | KubeEdge | ~2 min | CloudCore and EdgeCore |
| 4 | Overlay Network | ~3 min | Multus, OVS bridges, VXLAN |
| 5 | 5G Core | ~5 min | Open5GS network functions |
| 6 | UERANSIM | ~3 min | gNB and UE simulators |
| 7 | Observability | ~3 min | Prometheus, Loki, Grafana (optional) |

**Total deployment time**: ~18-21 minutes

## Running Phases

### Full Deployment

```bash
# Runs all phases
vagrant up
```

### Core Only (Default)

```bash
# Runs phases 1-5
DEPLOY_MODE=core_only vagrant up
```

### Specific Phases

```bash
vagrant ssh ansible
cd ~/ansible-ro

# Run specific phase
ansible-playbook phases/02-kubernetes/playbook.yml -i inventory.ini

# Run phases with tags
ansible-playbook phases/00-main-playbook.yml --tags phase4,phase5 -i inventory.ini
```

---

## Phase 1: Infrastructure

**Location**: `ansible/phases/01-infrastructure/`

### What it does
- Installs system packages (curl, wget, jq, etc.)
- Installs and configures Open vSwitch
- Configures kernel parameters (IP forwarding, etc.)
- Sets up systemd-networkd

### Key files
- `roles/infra_setup/tasks/main.yml`
- `roles/infra_setup/templates/ovs-system.conf.j2`

### Verify
```bash
vagrant ssh worker
sudo ovs-vsctl --version
```

---

## Phase 2: Kubernetes

**Location**: `ansible/phases/02-kubernetes/`

### What it does
- Deploys K3s server on master node
- Deploys K3s agents on worker and edge nodes
- Configures kubeconfig
- Verifies cluster health

### Key files
- `roles/k3s_master/tasks/main.yml`
- `roles/k3s_agent/tasks/main.yml`

### Verify
```bash
vagrant ssh master
kubectl get nodes
```

---

## Phase 3: KubeEdge

**Location**: `ansible/phases/03-kubeedge/`

### What it does
- Deploys CloudCore on master node
- Deploys EdgeCore on edge node
- Configures edge-cloud communication (WebSocket port 10000)
- Labels edge node

### Key files
- `roles/kubeedge_cloudcore/tasks/main.yml`
- `roles/kubeedge_edgecore/tasks/main.yml`

### Verify
```bash
kubectl get nodes
# Edge node should show: agent,edge roles
```

---

## Phase 4: Overlay Network

**Location**: `ansible/phases/04-overlay-network/`

### What it does
- Installs CNI binaries
- Deploys Multus CNI DaemonSets
- Creates OVS bridges (br-n1, br-n2, br-n3, br-n4, br-n6)
- Establishes VXLAN tunnels between worker and edge
- Creates NetworkAttachmentDefinitions (NADs)
- Creates per-cell networks

### Key files
- `roles/ovs_network_setup/tasks/main.yml`
- `roles/multus_install/tasks/main.yml`
- `roles/cell_network_setup/tasks/main.yml`
- `scripts/ovs-setup.sh`

### Verify
```bash
# Check OVS bridges
vagrant ssh worker
sudo ovs-vsctl show

# Check NADs
kubectl get net-attach-def -A
```

---

## Phase 5: 5G Core

**Location**: `ansible/phases/05-5g-core/`

### What it does
- Creates 5g namespace
- Deploys MongoDB
- Deploys Open5GS Network Functions:
  - NRF (NF Repository Function)
  - AMF (Access and Mobility Management)
  - SMF (Session Management Function)
  - UPF (User Plane Function) - cloud and edge
  - UDM, UDR, AUSF, PCF, BSF, NSSF
- Imports subscriber data
- Validates NF connectivity

### Key files
- `roles/infrastructure_setup/tasks/main.yml`
- `roles/nf_deployments/tasks/main.yml`
- `roles/subscriber_import/tasks/main.yml`
- `configs/*.yaml` - NF configurations

### Verify
```bash
kubectl get pods -n 5g
kubectl logs -n 5g deploy/amf -c amf --tail=20
```

---

## Phase 6: UERANSIM

**Location**: `ansible/phases/06-ueransim-mec/`

### What it does
- Creates discovery token for edge pods
- Deploys gNB (base station simulator)
- Deploys UE (user equipment simulator)
- Configures dynamic IP discovery via init containers
- Optionally deploys MEC applications

### Key files
- `roles/infrastructure_setup/tasks/main.yml` - Discovery token
- `roles/gnb_deployment/tasks/main.yml`
- `roles/ue_deployment/tasks/main.yml`
- `vars/topology.yml` - Cell and UE configuration

### Topology Configuration

```yaml
# vars/topology.yml
ueransim_topology:
  cells:
    - id: 1
      gnb:
        name: "gnb-1"
        node: "edge"
        nci: "0x000000010"
        tac: 1
      ues:
        - { id: 1, supi_suffix: "895", apn: "internet" }
        - { id: 2, supi_suffix: "896", apn: "internet" }
```

### Verify
```bash
# Check gNB
kubectl get pods -n 5g -l app=gnb-1

# Check UEs
kubectl get pods -n 5g -l app=ue

# Check AMF logs for registrations
kubectl logs -n 5g deploy/amf -c amf | grep -i "registered"
```

---

## Phase 7: Observability Stack (Optional)

**Purpose**: Deploy monitoring and logging infrastructure.

**Components**:
- Prometheus (metrics collection)
- Loki (log aggregation)
- Grafana (visualization)
- Node Exporter (node metrics)
- Promtail (log shipping)
- Traffic Capture (optional, PCAP)

### Deploy

```bash
vagrant ssh ansible
cd ~/ansible-ro

# Deploy observability stack
ansible-playbook phases/07-observability/playbook.yml -i inventory.ini

# With traffic capture enabled
ansible-playbook phases/07-observability/playbook.yml -i inventory.ini -e deploy_traffic_capture=true
```

### Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://192.168.56.11:30300 | admin / admin5g |
| Prometheus | http://192.168.56.11:30090 | - |

### Pre-built Dashboards

- **Cluster Overview** - Node health, resource usage
- **5G Core** - NF status, logs, metrics

### Verify

```bash
# Check pods
kubectl get pods -n monitoring

# Check Grafana
curl http://192.168.56.11:30300/api/health
```

---

## Troubleshooting Phases

### Re-run a Phase

```bash
vagrant ssh ansible
cd ~/ansible-ro
ansible-playbook phases/04-overlay-network/playbook.yml -i inventory.ini
```

### Skip Phases

```bash
ansible-playbook phases/00-main-playbook.yml --skip-tags phase6 -i inventory.ini
```

### Debug Mode

```bash
ansible-playbook phases/05-5g-core/playbook.yml -i inventory.ini -vvv
```

## Related Documentation

- [Architecture Overview](../architecture/overview.md)
- [Network Topology](../architecture/network-topology.md)
- [Physical RAN Integration](physical-ran.md)
- [Troubleshooting](../operations/troubleshooting.md)
