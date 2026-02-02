# Phase 07: Observability Stack

Deploys Prometheus, Loki, and Grafana for comprehensive monitoring and logging of the 5G testbed.

## Components

| Component | Purpose | Access |
|-----------|---------|--------|
| Prometheus | Metrics collection | http://192.168.56.11:30090 |
| Loki | Log aggregation | Internal only |
| Grafana | Visualization | http://192.168.56.11:30300 |
| Node Exporter | Node metrics | DaemonSet on all nodes |
| Promtail | Log shipping | DaemonSet on all nodes |
| Kube State Metrics | K8s object metrics | Master node |
| Traffic Capture | PCAP capture | Optional, DaemonSet |

## Deployment

```bash
# From Vagrant host
vagrant ssh ansible

# Deploy observability stack
cd /vagrant/ansible
ansible-playbook phases/07-observability/playbook.yml

# Or with traffic capture enabled
ansible-playbook phases/07-observability/playbook.yml -e deploy_traffic_capture=true
```

## Grafana Access

- **URL**: http://192.168.56.11:30300
- **Username**: admin
- **Password**: admin5g

### Pre-built Dashboards

1. **Cluster Overview** - Node health, CPU/memory, pod counts
2. **5G Core** - NF status, resource usage, logs

## Log Queries (Loki)

```logql
# All 5G namespace logs
{namespace="5g"}

# AMF errors
{namespace="5g", app="amf"} |= "error"

# gNB connection logs
{namespace="5g", app=~"gnb.*"} |~ "NG Setup|NGAP"

# UE registration
{namespace="5g", app=~"ue.*"} |~ "Registration|Attach"
```

## Metrics Queries (Prometheus)

```promql
# Pod restarts
sum by(pod) (kube_pod_container_status_restarts_total{namespace="5g"})

# Memory by pod
container_memory_usage_bytes{namespace="5g", container!=""}

# CPU usage %
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

## Traffic Capture

When enabled, captures 5G protocol traffic:

- **SCTP/38412** - NGAP (N2 interface)
- **UDP/2152** - GTP-U (N3 interface)  
- **UDP/8805** - PFCP (N4 interface)

PCAP files are stored in `/var/log/5g-captures/` on worker and edge nodes.

```bash
# List captures
vagrant ssh worker -c "ls /var/log/5g-captures/"

# Copy to host
vagrant scp worker:/var/log/5g-captures/*.pcap ./

# Analyze with Wireshark
wireshark ./5g-worker-20260201.pcap
```

## Resource Usage

Approximate resource consumption:

| Component | CPU | Memory |
|-----------|-----|--------|
| Prometheus | 200-500m | 256-512Mi |
| Loki | 200-500m | 256-512Mi |
| Grafana | 200-500m | 256-512Mi |
| Node Exporter | 50-100m | 64-128Mi |
| Promtail | 100-200m | 128-256Mi |
| Traffic Capture | 100-200m | 128-256Mi |

Total: ~1 CPU core, ~1.5GB RAM on worker node.
