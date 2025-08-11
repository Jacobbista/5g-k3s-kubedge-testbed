Vagrant.configure("2") do |config|
  # Mantieni la chiave "insecure": così l'ansible-controller può accedere con /home/vagrant/.ssh/id_rsa
  config.ssh.insert_key = false
  config.vm.box = "ubuntu/focal64"

  # Blocco riutilizzabile per scrivere /etc/hosts in modo idempotente e CORRETTO
  SHARED_HOSTS = <<-SCRIPT
cat >/tmp/hosts.add <<'EOF'
192.168.56.10 ansible-controller
192.168.56.11 kube-master
192.168.56.12 kube-worker-1
192.168.56.13 kube-worker-2
192.168.56.14 kube-worker-3
EOF

for h in ansible-controller kube-master kube-worker-1 kube-worker-2 kube-worker-3; do
  sudo sed -i "/[[:space:]]$h$/d" /etc/hosts
done
sudo tee -a /etc/hosts < /tmp/hosts.add
SCRIPT

  # kube-master
  config.vm.define "kube-master" do |m|
    m.vm.hostname = "kube-master"
    m.vm.network "private_network", ip: "192.168.56.11"
    m.vm.provider "virtualbox" do |vb|
      vb.name = "vagrant-k8s-repo_kube-master"
      vb.memory = 4096
      vb.cpus = 2
    end
    m.vm.provision "shell", inline: SHARED_HOSTS
  end

  # kube-worker-1
  config.vm.define "kube-worker-1" do |w|
    w.vm.hostname = "kube-worker-1"
    w.vm.network "private_network", ip: "192.168.56.12"
    w.vm.provider "virtualbox" do |vb|
      vb.name = "vagrant-k8s-repo_kube-worker-1"
      vb.memory = 4096
      vb.cpus = 2
    end
    w.vm.provision "shell", inline: SHARED_HOSTS
  end

  # kube-worker-2
  config.vm.define "kube-worker-2" do |w|
    w.vm.hostname = "kube-worker-2"
    w.vm.network "private_network", ip: "192.168.56.13"
    w.vm.provider "virtualbox" do |vb|
      vb.name = "vagrant-k8s-repo_kube-worker-2"
      vb.memory = 4096
      vb.cpus = 2
    end
    w.vm.provision "shell", inline: SHARED_HOSTS
  end

  # kube-worker-3
  config.vm.define "kube-worker-3" do |w|
    w.vm.hostname = "kube-worker-3"
    w.vm.network "private_network", ip: "192.168.56.14"
    w.vm.provider "virtualbox" do |vb|
      vb.name = "vagrant-k8s-repo_kube-worker-3"
      vb.memory = 4096
      vb.cpus = 2
    end
    w.vm.provision "shell", inline: SHARED_HOSTS
  end

  # ansible-controller (parte per ultimo)
  config.vm.define "ansible-controller" do |a|
    a.vm.hostname = "ansible-controller"
    a.vm.network "private_network", ip: "192.168.56.10"
    a.vm.provider "virtualbox" do |vb|
      vb.name = "vagrant-k8s-repo_ansible-controller"
      vb.memory = 2048
      vb.cpus = 2
    end

    # /etc/hosts corretto
    a.vm.provision "shell", inline: SHARED_HOSTS

    # Copia la insecure_private_key dal tuo host Windows al controller come id_rsa
    a.vm.provision "file",
      source: "#{ENV['USERPROFILE']}/.vagrant.d/insecure_private_key",
      destination: "/home/vagrant/.ssh/id_rsa"

    a.vm.provision "shell", inline: <<-SHELL
      sudo chown vagrant:vagrant /home/vagrant/.ssh/id_rsa
      sudo chmod 600 /home/vagrant/.ssh/id_rsa
      echo "🚀 Installing Ansible & tools..."
      sudo apt-get update -y
      sudo apt-get install -y ansible git curl
      echo "✅ Ansible ready. Running playbook automatically..."
      cd /vagrant/ansible
      ansible --version
      ansible-playbook -i inventory.ini playbook.yml
    SHELL
  end
end

