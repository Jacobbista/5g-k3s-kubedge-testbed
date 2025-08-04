# Vagrantfile
# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.ssh.insert_key = false
  config.vm.provider "virtualbox" do |v|
    v.memory = 8192
    v.cpus = 2
  end

  vms = {
    "ansible-controller" => { :ip => "192.168.56.10" },
    "k8s-master"         => { :ip => "192.168.56.11" },
    "k8s-worker-1"       => { :ip => "192.168.56.12" },
    "k8s-worker-2"       => { :ip => "192.168.56.13" },
    "k8s-worker-3"       => { :ip => "192.168.56.14" }
  }

  # Provisioning della chiave SSH per il controller
  config.vm.provision "file", source: "~/.vagrant.d/insecure_private_key", destination: ".ssh/id_rsa"

  vms.each do |hostname, properties|
    config.vm.define hostname do |node|
      node.vm.hostname = hostname
      node.vm.network "private_network", ip: properties[:ip]
      node.vm.synced_folder ".", "/vagrant"

      node.vm.provision "shell", inline: <<-SHELL
        echo "--- Eseguo provisioning su #{hostname} ---"
        echo "--- Aggiorno pacchetti ---"
        sudo apt-get update -y
        echo "--- Disabilito Firewall e Swap ---"
        sudo ufw disable
        sudo swapoff -a
        sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
        echo "--- Abilito IP Forwarding e Kernel Modules per Kubernetes ---"
        cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
        sudo modprobe overlay
        sudo modprobe br_netfilter
        cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-ip6tables = 1
net.bridge.bridge-nf-call-iptables = 1
net.ipv4.ip_forward = 1
EOF
        sudo sysctl --system
        echo "--- Configuro IP statico su interfaccia Host-Only ---"
        cat <<EOF | sudo tee /etc/netplan/02-vagrant-hostonly.yaml
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: no
      addresses: [#{properties[:ip]}/24]
EOF
        sudo netplan apply
        echo "--- Installo containerd (da repo Ubuntu) ---"
        sudo apt-get install -y containerd
        sudo mkdir -p /etc/containerd
        containerd config default | sudo tee /etc/containerd/config.toml
        sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
        sudo systemctl restart containerd
        echo "--- Installo Kubernetes v1.30 ---"
        sudo apt-get install -y apt-transport-https ca-certificates curl gpg
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
        echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
        sudo apt-get update
        sudo apt-get install -y kubelet=1.30.3-1.1 kubeadm=1.30.3-1.1 kubectl=1.30.3-1.1
        sudo apt-mark hold kubelet kubeadm kubectl
        if [ "#{hostname}" = "ansible-controller" ]; then
          echo "--- Installo Ansible ---"
          sudo apt-get install -y ansible sshpass
          sudo chown vagrant:vagrant /home/vagrant/.ssh/id_rsa
          sudo chmod 600 /home/vagrant/.ssh/id_rsa
          echo "--- Installo Ansible Galaxy Collections ---"
          sudo -u vagrant bash -c "ansible-galaxy collection install community.general"
          sudo -u vagrant bash -c "ansible-galaxy collection install kubernetes.core"
        fi
        echo "--- Provisioning completato per #{hostname} ---"
      SHELL
    end
  end
end