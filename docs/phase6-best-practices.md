# Phase 6 Best Practices & Design Principles

**Last Updated**: 2025-10-21  
**Purpose**: Architectural guidelines and design patterns for Phase 6

---

## Core Design Principles

### 1. **Declarative Over Imperative**

❌ **Anti-Pattern** (Imperative):

```bash
kubectl create deployment gnb --image=...
kubectl expose deployment gnb --port=38412
kubectl scale deployment gnb --replicas=3
```

✅ **Best Practice** (Declarative):

```yaml
# group_vars/all.yml
ueransim_topology:
  cells:
    - id: 1
      gnb: { name: "gnb-1", ... }
      ues: [{ ... }, { ... }]
```

**Rationale**:

- Single source of truth
- Version-controllable (Git)
- Repeatable deployments
- Easier to reason about state

---

### 2. **API-Driven Operations**

❌ **Anti-Pattern** (Shell commands):

```yaml
- name: Deploy gNB
  shell: |
    kubectl apply -f /tmp/gnb.yaml
    kubectl wait --for=condition=ready pod -l app=gnb
```

✅ **Best Practice** (Kubernetes API):

```yaml
- name: Deploy gNB
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: apps/v1
      kind: StatefulSet
      # ...

- name: Wait for gNB readiness
  kubernetes.core.k8s_info:
    kind: StatefulSet
    name: gnb-1
  register: gnb
  until: gnb.resources[0].status.readyReplicas >= 1
  retries: 30
```

**Rationale**:

- Idempotent operations
- Proper error handling
- No string parsing brittleness
- Ansible diff mode works correctly

---

### 3. **No Runtime Configuration Patching**

❌ **Anti-Pattern** (sed/awk in container):

```bash
# Inside UE container
GNB_IP=$(getent hosts gnb | awk '{print $1}')
sed -i "s/{{GNB_IP}}/$GNB_IP/" /config/ue.yaml
nr-ue -c /config/ue.yaml
```

✅ **Best Practice** (Init container + templating):

```yaml
initContainers:
  - name: config-generator
    image: ueransim
    command: ["python", "/scripts/generate_config.py"]
    env:
      - name: REPLICA_INDEX
        valueFrom:
          fieldRef:
            fieldPath: metadata.name
    volumeMounts:
      - name: config-runtime
        mountPath: /config

containers:
  - name: ue
    command: ["nr-ue", "-c", "/config/ue-$(REPLICA_INDEX).yaml"]
```

**Rationale**:

- Config generation is auditable (logs)
- Init container fails fast (not silent errors)
- Main container is immutable (no side effects)
- Easier debugging (inspect config in volume)

---

### 4. **Stable Identity via StatefulSets**

❌ **Anti-Pattern** (Deployment with replicas > 1):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ue
spec:
  replicas: 4 # ❌ All UEs have same SUPI!
```

✅ **Best Practice** (StatefulSet with unique configs):

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ue-cell-1
spec:
  replicas: 4 # ue-cell-1-0, ue-cell-1-1, ...
  template:
    spec:
      initContainers:
        - name: config-gen
          # Generate config based on pod ordinal
          # ue-cell-1-0 → SUPI=...895
          # ue-cell-1-1 → SUPI=...896
```

**Rationale**:

- Predictable DNS names (`ue-cell-1-0.ue-cell-1.5g.svc.cluster.local`)
- Stable network identity (IP persists across restarts)
- Ordered startup (if needed)
- Per-replica volumes (if needed)

---

### 5. **Network Isolation via NADs**

❌ **Anti-Pattern** (All gNBs share one NAD):

```yaml
# All gNBs use n2-net (10.202.0.0/24)
# → Broadcast domain pollution
# → Can't simulate cell isolation
```

✅ **Best Practice** (One NAD per cell):

```yaml
# Cell 1: n2-cell-1 (10.202.1.0/24)
# Cell 2: n2-cell-2 (10.202.2.0/24)
# → L2 isolation
# → Realistic cell behavior
```

**Rationale**:

- Prevents ARP/broadcast interference
- Enables handover simulations (move UE between NADs)
- Matches real-world RAN architecture
- Easier troubleshooting (tcpdump on specific bridge)

---

### 6. **Service Discovery: Headless + Endpoints**

❌ **Anti-Pattern** (ClusterIP + kube-proxy):

```yaml
# UE resolves gnb.5g.svc.cluster.local
# → Gets ClusterIP (10.43.x.x)
# → kube-proxy NATs to Pod IP
# → Extra hop, can't use Multus IP directly
```

✅ **Best Practice** (Headless Service + Multus Endpoints):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: gnb-1
spec:
  clusterIP: None # Headless
---
# CronJob syncs Multus N2 IPs to Endpoints
apiVersion: v1
kind: Endpoints
metadata:
  name: gnb-1
subsets:
  - addresses:
      - ip: 10.202.1.11 # Multus N2 IP (not Pod IP)
```

**Rationale**:

- UE connects directly to gNB's N2 interface
- No kube-proxy overhead
- Matches 3GPP protocols (NGAP expects direct IP)
- Works across nodes (VXLAN bridges N2)

---

### 7. **Automated Subscriber Management**

❌ **Anti-Pattern** (Manual JSON editing):

```bash
# Edit ansible/phases/05-5g-core/subscribers.json
# Add new IMSI manually
# Re-run Phase 5
ansible-playbook phases/05-5g-core/playbook.yml
```

✅ **Best Practice** (Job reads topology, syncs MongoDB):

```yaml
# Topology is single source of truth
ueransim_topology:
  cells:
    - ues:
        - supi_suffix: "895" # Auto-registered

# Job generates subscribers
apiVersion: batch/v1
kind: Job
metadata:
  name: subscriber-sync
spec:
  template:
    spec:
      containers:
        - name: sync
          command: ["python", "/scripts/sync_subscribers.py"]
          # Reads topology, upserts to MongoDB
```

**Rationale**:

- Single source of truth (topology YAML)
- Idempotent (safe to re-run)
- No manual DB operations
- Scales to hundreds of UEs

---

## Kubernetes Best Practices

### 1. **Use init Containers for Dependencies**

❌ **Anti-Pattern**:

```yaml
containers:
  - name: ue
    command:
      - /bin/bash
      - -c
      - |
        while ! nc -z gnb-1 38412; do
          sleep 1
        done
        nr-ue -c /config/ue.yaml
```

✅ **Best Practice**:

```yaml
initContainers:
  - name: wait-for-gnb
    image: busybox
    command: ["sh", "-c", "until nc -z gnb-1 38412; do sleep 1; done"]

containers:
  - name: ue
    command: ["nr-ue", "-c", "/config/ue.yaml"]
```

**Rationale**:

- Init container failure is visible in pod status
- Main container logs are clean (no wait loops)
- Kubernetes restart policy works correctly

---

### 2. **Proper Readiness Probes**

❌ **Anti-Pattern** (Process check):

```yaml
readinessProbe:
  exec:
    command: ["pgrep", "-f", "nr-gnb"]
```

Problem: Process exists but might not be registered with AMF.

✅ **Best Practice** (Protocol-level check):

```yaml
readinessProbe:
  exec:
    command:
      - /bin/sh
      - -c
      - |
        # Check gNB is listening on NGAP port
        ss -S -lnt | grep -q ':38412' && \
        # Check NG Setup was successful (parse logs)
        grep -q 'NG Setup successful' /var/log/gnb.log
  initialDelaySeconds: 10
  periodSeconds: 5
```

**Rationale**:

- Readiness = "ready to serve traffic"
- Process running ≠ registered with AMF
- Service endpoints only include ready pods

---

### 3. **Resource Requests/Limits**

✅ **Best Practice**:

```yaml
containers:
  - name: gnb
    resources:
      requests:
        cpu: "500m"
        memory: "512Mi"
      limits:
        cpu: "1000m"
        memory: "1Gi"
```

**Rationale**:

- Prevents resource starvation
- Enables proper QoS class
- Scheduler can make better decisions
- OOM kills are predictable

---

### 4. **Liveness vs Readiness**

```yaml
# Liveness: Should pod be restarted?
livenessProbe:
  exec:
    command: ["pgrep", "-f", "nr-gnb"]
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 3 # Restart after 30s of failures

# Readiness: Should pod receive traffic?
readinessProbe:
  tcpSocket:
    port: 38412
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 2 # Remove from endpoints after 10s
```

**Rationale**:

- Liveness = process health (rare failures)
- Readiness = protocol health (temporary failures)
- Different thresholds prevent flapping

---

## Python Best Practices (Sync Jobs)

### 1. **Use Kubernetes Python Client**

❌ **Anti-Pattern**:

```python
import subprocess
result = subprocess.run(["kubectl", "get", "pods", "-o", "json"], capture_output=True)
pods = json.loads(result.stdout)
```

✅ **Best Practice**:

```python
from kubernetes import client, config

config.load_incluster_config()
v1 = client.CoreV1Api()
pods = v1.list_namespaced_pod("5g")
```

**Rationale**:

- Native API, no subprocess overhead
- Proper error handling (exceptions)
- Type safety (IDE autocomplete)
- Watches support (real-time updates)

---

### 2. **Idempotent Operations**

✅ **Best Practice**:

```python
def sync_endpoint(name, ip):
    """Idempotent: create if missing, update if exists."""
    try:
        v1.patch_namespaced_endpoints(name, "5g", endpoints)
        logger.info(f"Updated Endpoints {name}")
    except ApiException as e:
        if e.status == 404:
            v1.create_namespaced_endpoints("5g", endpoints)
            logger.info(f"Created Endpoints {name}")
        else:
            raise
```

**Rationale**:

- Safe to re-run (CronJob, manual trigger)
- Handles API server restarts gracefully
- No "already exists" errors

---

### 3. **Structured Logging**

❌ **Anti-Pattern**:

```python
print("Updated endpoint gnb-1 with IP 10.202.1.11")
```

✅ **Best Practice**:

```python
import logging
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("Endpoint synced", extra={
    "endpoint_name": "gnb-1",
    "multus_ip": "10.202.1.11",
    "cell_id": 1
})
```

**Rationale**:

- Parseable by Loki/Elasticsearch
- Filterable (show only cell-1 logs)
- Structured data (JSON export)

---

## Ansible Best Practices

### 1. **Template Organization**

```
roles/gnb_deployment/
├── defaults/main.yml          # Variables
├── tasks/
│   ├── main.yml               # Orchestration
│   ├── validate.yml           # Pre-flight checks
│   └── cleanup.yml            # Optional cleanup
└── templates/
    ├── gnb-statefulset.yaml.j2
    ├── gnb-config.yaml.j2
    └── gnb-service.yaml.j2
```

**Rationale**:

- Separation of concerns
- Reusable validation tasks
- Clear template purpose

---

### 2. **Variable Precedence**

```yaml
# group_vars/all.yml (global defaults)
ueransim_image: "jacobbista/ueransim:latest"

# roles/gnb_deployment/defaults/main.yml (role defaults)
gnb_replicas: 1

# playbook.yml (runtime overrides)
- hosts: masters
  vars:
    gnb_replicas: 3  # Override for this run
```

**Rationale**:

- Defaults in `roles/*/defaults/main.yml`
- Global config in `group_vars/all.yml`
- Runtime overrides in playbook or CLI (`-e`)

---

### 3. **Loops with Retries**

❌ **Anti-Pattern**:

```yaml
- name: Wait for pods
  shell: kubectl wait --for=condition=ready pod -l app=gnb
  retries: 30
  delay: 10
```

✅ **Best Practice**:

```yaml
- name: Wait for gNB pods ready
  kubernetes.core.k8s_info:
    kind: Pod
    namespace: 5g
    label_selectors: ["app=gnb-{{ item.id }}"]
  register: pods
  until: >-
    pods.resources | length > 0 and
    (pods.resources | selectattr('status.phase', 'equalto', 'Running') | list | length) >= 1
  retries: 30
  delay: 10
  loop: "{{ ueransim_topology.cells }}"
  loop_control:
    label: "{{ item.gnb.name }}"
```

**Rationale**:

- Native API (no shell)
- Explicit conditions (no exit code guessing)
- Loop control improves output readability

---

## Security Best Practices

### 1. **Least-Privilege RBAC**

❌ **Anti-Pattern**:

```yaml
# ServiceAccount with cluster-admin
subjects:
  - kind: ServiceAccount
    name: endpoints-sync
clusterRoleRef:
  name: cluster-admin # ❌ Too permissive
```

✅ **Best Practice**:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role # Namespace-scoped
metadata:
  name: endpoints-sync
  namespace: 5g
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list"] # Read-only
  - apiGroups: [""]
    resources: ["endpoints"]
    verbs: ["get", "create", "patch"] # Only what's needed
```

**Rationale**:

- Principle of least privilege
- Namespace-scoped (not cluster-wide)
- Explicit resource types (not `resources: ["*"]`)

---

### 2. **Secret Management**

❌ **Anti-Pattern**:

```yaml
# Hardcoded in ConfigMap
apiVersion: v1
kind: ConfigMap
data:
  ue.yaml: |
    key: 8baf473f2f8fd09487cccbd7097c6862  # ❌ Visible in etcd
```

✅ **Best Practice** (for production):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: ue-credentials
type: Opaque
stringData:
  key: "8baf473f2f8fd09487cccbd7097c6862"
  op: "11111111111111111111111111111111"
---
# Mount as volume
volumeMounts:
  - name: credentials
    mountPath: /secrets
    readOnly: true
```

**Rationale**:

- Secrets encrypted at rest (if configured)
- Not visible in `kubectl describe`
- Can integrate with external secret stores (Vault, AWS Secrets Manager)

**Note**: For testbed use, ConfigMap is acceptable (no real subscriber data).

---

### 3. **Container Security**

✅ **Best Practice**:

```yaml
securityContext:
  # Don't run as root
  runAsNonRoot: true
  runAsUser: 1000

  # Drop unnecessary capabilities
  capabilities:
    drop: ["ALL"]
    add: ["NET_ADMIN"] # Only what's needed for TUN interface

  # Read-only root filesystem
  readOnlyRootFilesystem: true

  # Prevent privilege escalation
  allowPrivilegeEscalation: false
```

**Rationale**:

- Defense in depth
- Limits blast radius of compromised container
- Compliance with security benchmarks (CIS)

**Note**: UERANSIM currently requires `privileged: true` for TUN interfaces. Future work: use `CAP_NET_ADMIN` only.

---

## Monitoring & Observability

### 1. **Structured Logs**

✅ **Best Practice**:

```json
{
  "timestamp": "2025-10-20T12:34:56Z",
  "level": "INFO",
  "component": "gnb",
  "cell_id": 1,
  "event": "ng_setup_complete",
  "amf_ip": "10.202.0.100",
  "duration_ms": 123
}
```

**Rationale**:

- Parseable by Loki/ELK
- Filterable (show only errors, specific cell)
- Aggregatable (avg duration by cell)

---

### 2. **Prometheus Metrics**

✅ **Best Practice** (future enhancement):

```python
from prometheus_client import Counter, Histogram

ue_registrations = Counter('ue_registrations_total', 'Total UE registrations', ['cell_id', 'status'])
pdu_session_duration = Histogram('pdu_session_duration_seconds', 'PDU session establishment time')

# In code
ue_registrations.labels(cell_id=1, status='success').inc()
pdu_session_duration.observe(0.123)
```

**Rationale**:

- Time-series data for KPIs
- Integration with Grafana
- Alerting (Prometheus Alertmanager)

---

### 3. **Health Endpoints**

✅ **Best Practice**:

```yaml
# gNB health endpoint (future)
containers:
  - name: gnb
    ports:
      - containerPort: 9090
        name: metrics
    livenessProbe:
      httpGet:
        path: /healthz
        port: 9090
```

**Rationale**:

- Kubernetes-native health checks
- Metrics endpoint for Prometheus
- Separation of health (9090) and protocol (38412)

---

## Testing Best Practices

### 1. **Unit Tests for Templates**

```python
# tests/test_gnb_template.py
import yaml
from jinja2 import Template

def test_gnb_statefulset_renders():
    template = Template(open('roles/gnb_deployment/templates/gnb-statefulset.yaml.j2').read())

    context = {
        'ueransim_topology': {
            'cells': [{'id': 1, 'gnb': {'name': 'gnb-1', 'node': 'worker'}}]
        }
    }

    rendered = template.render(context)
    docs = list(yaml.safe_load_all(rendered))

    assert len(docs) == 2  # Service + StatefulSet
    assert docs[1]['kind'] == 'StatefulSet'
    assert docs[1]['metadata']['name'] == 'gnb-1'
```

**Rationale**:

- Catch template errors early
- Fast feedback (no cluster needed)
- CI/CD integration

---

### 2. **Integration Tests**

```python
# tests/test_gnb_deployment.py
def test_gnb_pod_starts(k8s_client):
    # Wait for pod
    pods = k8s_client.list_namespaced_pod('5g', label_selector='app=gnb-1')
    assert len(pods.items) == 1

    # Check pod is ready
    assert pods.items[0].status.phase == 'Running'

    # Check Multus annotations
    network_status = json.loads(
        pods.items[0].metadata.annotations['k8s.v1.cni.cncf.io/network-status']
    )
    assert any(net['interface'] == 'n2' for net in network_status)
```

**Rationale**:

- Tests actual Kubernetes behavior
- Validates Multus integration
- End-to-end confidence

---

## Documentation Best Practices

### 1. **Runbooks for Common Tasks**

````markdown
# docs/runbooks/scale-ue-deployment.md

## Scale UE Deployment

**Scenario**: Add 2 more UEs to cell-1

**Steps**:

1. Edit `ansible/group_vars/all.yml`:
   ```yaml
   ueransim_topology:
     cells:
       - id: 1
         ues:
           - { id: 3, supi_suffix: "897" } # Add this
           - { id: 4, supi_suffix: "898" } # Add this
   ```
````

2. Run playbook:

   ```bash
   ansible-playbook phases/06-ueransim-mec/playbook.yml
   ```

3. Verify:
   ```bash
   kubectl get sts -n 5g ue-cell-1
   # READY 4/4
   ```

````

---

### 2. **Architecture Decision Records (ADRs)**

```markdown
# docs/adr/001-use-statefulsets-for-ues.md

## ADR 001: Use StatefulSets for UE Deployments

**Status**: Accepted
**Date**: 2025-10-20

### Context
UEs need stable identities (SUPI) and predictable DNS names.

### Decision
Use StatefulSets instead of Deployments.

### Consequences
- ✅ Stable network identity
- ✅ Ordered startup
- ❌ Slower rolling updates (sequential)
````

---

## Conclusion

This document outlines best practices for Phase 6 redesign. Key principles:

1. **Declarative over imperative**: Single source of truth (topology YAML)
2. **API-driven operations**: No shell scripts, use Kubernetes API
3. **Stable identity**: StatefulSets for predictable behavior
4. **Network isolation**: Per-cell NADs for realistic simulations
5. **Automation**: Subscriber sync, Endpoints sync via Jobs/CronJobs
6. **Observability**: Structured logs, metrics, health checks
7. **Security**: RBAC, least privilege, secret management
8. **Testing**: Unit tests for templates, integration tests for behavior

Following these practices ensures a **production-grade, maintainable, and scalable** 5G testbed.

---

## References

- [Phase 6 README](../ansible/phases/06-ueransim-mec/README.md) - Current implementation
- [Phase 6 Refactoring](../ansible/phases/06-ueransim-mec/REFACTORING.md) - Implementation details
- [gNB Endpoints Sync](../ansible/phases/06-ueransim-mec/roles/endpoints_sync/README.md) - DNS resolution architecture
