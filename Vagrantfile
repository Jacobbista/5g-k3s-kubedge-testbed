Vagrant.configure("2") do |config|
  # Mantieni la chiave "insecure": così l'ansible-controller può accedere con /home/vagrant/.ssh/id_rsa
  config.ssh.insert_key = false
  config.vm.box = "ubuntu/jammy64"  # Ubuntu 22.04 LTS

  # Blocco riutilizzabile per scrivere /etc/hosts in modo idempotente e CORRETTO
  SHARED_HOSTS = <<-SCRIPT
cat >/tmp/hosts.add <<'EOF'
192.168.56.10 ansible-controller
192.168.56.11 kube-master
192.168.56.12 kube-worker
192.168.56.13 kubeedge-edge
EOF

for h in ansible-controller kube-master kube-worker kubeedge-edge; do
  sudo sed -i "/[[:space:]]$h$/d" /etc/hosts
done
sudo tee -a /etc/hosts < /tmp/hosts.add
SCRIPT

  # kube-master
  config.vm.define "kube-master" do |m|
    m.vm.hostname = "kube-master"
    m.vm.network "private_network", ip: "192.168.56.11"
    m.vm.provider "virtualbox" do |vb|
      vb.name = "healthcare-5g-testbed_kube-master"
      vb.memory = 4096
      vb.cpus = 2
    end
    m.vm.provision "shell", inline: SHARED_HOSTS
  end

  # kube-worker
  config.vm.define "kube-worker" do |w|
    w.vm.hostname = "kube-worker"
    w.vm.network "private_network", ip: "192.168.56.12"
    w.vm.provider "virtualbox" do |vb|
      vb.name = "healthcare-5g-testbed_kube-worker"
      vb.memory = 4096
      vb.cpus = 2
    end
    w.vm.provision "shell", inline: SHARED_HOSTS
  end

  # kubeedge-edge (nodo edge)
  config.vm.define "kubeedge-edge" do |e|
    e.vm.hostname = "kubeedge-edge"
    e.vm.network "private_network", ip: "192.168.56.13"
    e.vm.provider "virtualbox" do |vb|
      vb.name = "healthcare-5g-testbed_kubeedge-edge"
      vb.memory = 4096
      vb.cpus = 2
    end
    e.vm.provision "shell", inline: SHARED_HOSTS
  end

  # ansible-controller (parte per ultimo)
  config.vm.define "ansible-controller" do |a|
    a.vm.hostname = "ansible-controller"
    a.vm.network "private_network", ip: "192.168.56.10"
    a.vm.provider "virtualbox" do |vb|
      vb.name = "healthcare-5g-testbed_ansible-controller"
      vb.memory = 2048
      vb.cpus = 2
    end

    # /etc/hosts corretto
    a.vm.provision "shell", inline: SHARED_HOSTS

    a.vm.provision "shell", inline: <<-SHELL
      # Copia le chiavi SSH delle altre VM per Ansible
      mkdir -p /home/vagrant/.ssh
      sudo cp /home/vagrant/.ssh/authorized_keys /home/vagrant/.ssh/id_rsa.pub
      sudo wget -O /home/vagrant/.ssh/id_rsa https://raw.githubusercontent.com/hashicorp/vagrant/main/keys/vagrant
      sudo chown vagrant:vagrant /home/vagrant/.ssh/id_rsa /home/vagrant/.ssh/id_rsa.pub
      sudo chmod 600 /home/vagrant/.ssh/id_rsa
      sudo chmod 644 /home/vagrant/.ssh/id_rsa.pub
      echo "🚀 Installing Ansible & tools..."
      sudo apt-get update -y
      sudo apt-get install -y ansible git curl python3-pip
      sudo pip3 install kubernetes openshift
      echo "✅ Ansible ready. Running playbook automatically..."
      cd /vagrant/ansible
      ansible --version
      echo "🔧 Waiting for all VMs to be ready..."
      sleep 30
      echo "🚀 Starting Healthcare 5G Testbed deployment..."
      ansible-playbook -i inventory.ini playbook.yml
      echo "🎉 Healthcare 5G Testbed deployment completed!"
      echo "📊 Access your cluster: vagrant ssh kube-master"
      echo "🏥 Check Open5GS: kubectl get pods -n open5gs"
      echo "🔗 Check KubeEdge: kubectl get nodes -l node-role.kubernetes.io/edge="
    SHELL
  end
end

