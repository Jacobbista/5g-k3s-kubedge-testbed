# Healthcare 5G Testbed con Kubernetes e KubeEdge

Testbed completo per simulare un ambiente sanitario 5G con orchestrazione edge intelligente tramite KubeEdge e core network Open5GS.

## 🏥 Scenario del Progetto

Il testbed simula un ospedale intelligente con:
- **Core Network 5G**: Open5GS per gestione UE, autenticazione e routing
- **Edge Computing**: KubeEdge per orchestrazione intelligente dei servizi edge
- **Dispositivi IoT Medici**: Simulazione di monitor cardiaci, ventilatori, defibrillatori
- **Gestione Autonoma del Carico**: KubeEdge trasferisce automaticamente i container in base al carico
- **Metriche e Monitoraggio**: Dashboard per visualizzare performance e latenza

## 🚀 Avvio Rapido

```bash
# Clona e avvia tutto con un comando
git clone <repository>
cd 5g-k8s-testbed-vagrant-ansible-fullautodeploy
vagrant up
```

Il provisioning automatico:
1. Crea 4 VM Ubuntu 22.04
2. Configura il cluster Kubernetes con KubeEdge
3. Installa Open5GS con persistent volumes
4. Configura OVS-CNI per interfacce N1/N2/N3
5. Deploya servizi IoT medici simulati
6. Avvia test di carico automatici

## 🏗️ Architettura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Ansible         │    │ Kubernetes      │    │ KubeEdge        │
│ Controller      │    │ Master          │    │ Edge Node       │
│ 192.168.56.10  │    │ 192.168.56.11   │    │ 192.168.56.13   │
│                 │    │                 │    │                 │
│ - Orchestrazione│    │ - API Server    │    │ - Edge Runtime  │
│ - Playbook      │    │ - etcd          │    │ - Device Twin   │
│ - Inventory     │    │ - Scheduler     │    │ - IoT Services  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                │
                       ┌─────────────────┐
                       │ Kubernetes      │
                       │ Worker          │
                       │ 192.168.56.12   │
                       │                 │
                       │ - Kubelet       │
                       │ - Container     │
                       │ - Open5GS       │
                       └─────────────────┘
```

## 📊 Funzionalità Testate

- **Orchestrazione Edge**: KubeEdge gestisce automaticamente il deployment
- **Load Balancing**: Trasferimento automatico di container in base al carico
- **5G Core Network**: Open5GS con interfacce N1/N2/N3/N4 funzionanti
- **Persistent Storage**: MongoDB con persistent volumes
- **Network Functions**: OVS-CNI per interfacce di rete 5G
- **Monitoring**: Metriche di performance e latenza edge-cloud

## 🔧 Requisiti

- Vagrant 2.2+
- VirtualBox 6.0+
- 16GB RAM disponibile
- 50GB spazio disco

## 📁 Struttura del Progetto

```
.
├── Vagrantfile                 # Configurazione VM e provisioning automatico
├── README.md                   # Documentazione completa
└── ansible/
    ├── ansible.cfg            # Configurazione Ansible
    ├── inventory.ini          # Inventory delle macchine
    ├── playbook.yml           # Playbook principale
    └── roles/
        ├── setup/             # Setup base (containerd, kube tools)
        ├── master/            # Configurazione master Kubernetes
        ├── workers/           # Configurazione worker Kubernetes
        ├── kubeedge/          # Installazione e configurazione KubeEdge
        ├── open5gs/           # Deploy Open5GS con persistent volumes
        ├── monitoring/        # Installazione dashboard e metriche
        └── healthcare/        # Deploy servizi IoT medici simulati
```

## 🧪 Test e Verifica

Dopo il deployment:

```bash
# Accedi al master
vagrant ssh kube-master

# Verifica cluster
kubectl get nodes
kubectl get pods -A

# Verifica KubeEdge
kubectl get nodes -l node-role.kubernetes.io/edge=
kubectl get configmap -n kubeedge

# Verifica Open5GS
kubectl get pods -n open5gs
kubectl get pvc -n open5gs

# Accedi al dashboard
kubectl port-forward -n kubernetes-dashboard service/kubernetes-dashboard 8080:443
# Apri http://localhost:8080 nel browser
```

## 📈 Metriche e Performance

Il testbed genera automaticamente:
- Latenza edge-cloud
- Throughput delle interfacce 5G
- Utilizzo CPU/RAM sui nodi
- Tempo di trasferimento container KubeEdge
- Performance del core network Open5GS

## 🚨 Troubleshooting

- **VM non si avviano**: Verifica che VirtualBox sia installato e funzionante
- **Problemi di rete**: Controlla che le porte 192.168.56.x non siano occupate
- **Errori Ansible**: Verifica che le VM siano completamente avviate prima del provisioning

## 📝 Licenza

MIT License - Libero utilizzo per scopi educativi e di ricerca.
