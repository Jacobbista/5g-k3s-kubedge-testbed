# vagrant-k8s-repo-completo

Cluster Kubernetes in Vagrant (Ubuntu 20.04) con join **automatizzato** dei worker e deploy **Open5GS** via Helm.

## Avvio rapido

```bash
vagrant up
```

Alla fine del provisioning, Ansible:
- prepara tutti i nodi (containerd, kubeadm/kubelet/kubectl);
- inizializza il **master** (`kubeadm init`) e installa **Calico**;
- **genera automaticamente** il token di join e iscrive i **worker**;
- installa **Helm** sul master e rilascia **Open5GS** nel namespace `5g`.

Per rientrare sul master:
```bash
vagrant ssh kube-master
kubectl get nodes
kubectl -n 5g get pods
```

## Layout

```
.
├── Vagrantfile
└── ansible
    ├── ansible.cfg
    ├── inventory.ini
    ├── playbook.yml
    └── roles
        ├── master
        │   ├── tasks/main.yml
        │   └── templates/kubeadm-config.yaml.j2
        ├── open5gs
        │   └── tasks/main.yml
        ├── setup
        │   └── tasks/main.yml
        └── workers
            └── tasks/main.yml
```
