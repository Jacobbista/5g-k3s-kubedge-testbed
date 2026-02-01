# Physical RAN Integration

How to connect a real femtocell (e.g., nCELL-F2240) instead of UERANSIM.

## How It Works

```
                    WORKER VM                           PHYSICAL NETWORK
              ┌─────────────────────┐              
              │  5G Core (Open5GS)  │              
              │  AMF: 10.202.x.x    │◄─────────────┐
              │  UPF: 10.203.x.x    │◄───────────┐ │
              └─────────┬───────────┘            │ │
                        │                        │ │
              ┌─────────┴───────────┐            │ │
              │     OVS Bridges     │            │ │
              │  br-n2 ←→ br-ran    │────────────┤ │  N3 (GTP-U)
              │  br-n3 ←→ br-ran    │────────────┘ │  N2 (NGAP)
              └─────────┬───────────┘              │
                        │ enp0s9                   │
                        │ 192.168.57.1             │
                        └──────────────────────────┼─────────────────┐
                                                   │                 │
                                          ┌────────┴───────┐         │
                                          │   FEMTOCELL    │    5G Radio
                                          │ 192.168.57.10  │─────────┘
                                          └────────────────┘
```

The femtocell connects to the **same overlay network** used by UERANSIM, not the management network.

---

## 1. Enable Integration

### Step 1: Configure Ansible

Edit `ansible/group_vars/all.yml`:

```yaml
ran_bridge_mode: n2_n3    # Was: disabled
ran_interface: ""         # Auto-detect
```

### Step 2: Apply Changes

```bash
# If you haven't done vagrant up yet:
vagrant up

# If cluster is already running, re-run OVS only:
vagrant ssh ansible
cd ~/ansible-ro
ansible-playbook phases/04-overlay-network/playbook.yml -i inventory.ini --tags overlay
```

### Step 3: Get Core IPs

```bash
vagrant ssh master

# Get AMF N2 IP
kubectl get pod -n 5g -l app=amf -o yaml | grep -A50 "network-status" | grep -E "10\.202\." | head -1

# Get UPF N3 IP
kubectl get pod -n 5g -l app=upf-cloud -o yaml | grep -A50 "network-status" | grep -E "10\.203\." | head -1
```

Example output:
```
AMF N2: 10.202.1.10
UPF N3: 10.203.0.100
```

---

## 2. Configure Femtocell

### Network

| Parameter | Value |
|-----------|-------|
| Femtocell IP | `192.168.57.10/24` |
| Gateway | `192.168.57.1` (worker) |
| Route to N2 | `10.202.0.0/16 via 192.168.57.1` |
| Route to N3 | `10.203.0.0/16 via 192.168.57.1` |

### 5G Parameters

| Parameter | Value |
|-----------|-------|
| MCC | `001` |
| MNC | `01` |
| TAC | `1` |
| AMF IP | From step 3 (e.g., `10.202.1.10`) |
| AMF Port | `38412` |
| S-NSSAI | SST=1, SD=0x000001 |

---

## 3. Physical Connection

### With VirtualBox (development)

The femtocell must be on the same network as the worker. Options:

**A) USB Ethernet Adapter**
```
[Host PC] 
    └── USB Ethernet ─── [Switch] ─── Femtocell (192.168.57.10)
                              │
    [VirtualBox]              │
        └── Worker VM ────────┘ (internal network "5g-ran-network")
```

**B) Bridge to physical interface**

Edit Vagrantfile, change `virtualbox__intnet` to a bridge:
```ruby
m.vm.network "public_network", bridge: "eth0"  # Your physical NIC
```

### Bare Metal (production)

Connect the femtocell directly to the worker's second NIC.

---

## 4. Verify

### Is OVS bridge active?

```bash
vagrant ssh worker
sudo ovs-vsctl show | grep -A5 br-ran
```

Expected:
```
Bridge br-ran
    Port enp0s9
    Port patch-ran-n2
    Port patch-ran-n3
```

### Can femtocell reach AMF?

```bash
# From femtocell
ping 192.168.57.1    # Worker
ping 10.202.1.10     # AMF (through OVS bridge)
```

### Does AMF see the gNB?

```bash
kubectl logs -f -l app=amf -n 5g | grep -i gnb
```

Expected:
```
[Added] Number of gNBs is now 1
```

---

## 5. Switch Back to UERANSIM

```yaml
# ansible/group_vars/all.yml
ran_bridge_mode: disabled
```

```bash
vagrant ssh ansible
cd ~/ansible-ro
ansible-playbook phases/04-overlay-network/playbook.yml -i inventory.ini --tags overlay
ansible-playbook phases/06-ueransim-mec/playbook.yml -i inventory.ini
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ping 10.202.x.x` fails | Missing route | Add route on femtocell |
| AMF doesn't see gNB | PLMN mismatch | Check MCC/MNC/TAC |
| SCTP connection refused | Module not loaded | `sudo modprobe sctp` on worker |
| UE rejected | Missing subscriber | Add IMSI to MongoDB |

### Useful Commands

```bash
# Check configured PLMN
kubectl get cm amf-config -n 5g -o yaml | grep -A3 plmn

# Check subscribers
kubectl exec -it deploy/mongodb -n 5g -- mongosh open5gs --eval "db.subscribers.find()"

# AMF logs
kubectl logs -f -l app=amf -n 5g
```
