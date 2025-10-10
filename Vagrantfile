# Vagrantfile (pulito, conservativo)
Vagrant.configure("2") do |config|
  config.ssh.insert_key = true
  config.vm.box_check_update = false

  nodes = {
    "master"  => { cpu: 4, mem: 4096, ip: "192.168.56.10", box: "ubuntu/jammy64" },
    "worker"  => { cpu: 8, mem: 8192, ip: "192.168.56.11", box: "ubuntu/jammy64" },
    "edge"    => { cpu: 4, mem: 4096, ip: "192.168.56.12", box: "ubuntu/jammy64" },
    "ansible" => { cpu: 2, mem: 1024, ip: "192.168.56.13", box: "ubuntu/jammy64" }
  }

  nodes.each do |name, spec|
    config.vm.define name, primary: (name == "ansible") do |m|
      m.vm.hostname = name
      m.vm.network "private_network", ip: spec[:ip]
      m.vm.box = spec[:box]

      m.vm.provider "virtualbox" do |vb|
        vb.cpus   = spec[:cpu]
        vb.memory = spec[:mem]
        vb.name = "#{name}-5g-k8s-testbed"
      end

      if name != "ansible"
        m.vm.synced_folder ".", "/vagrant", disabled: true
      else
        m.vm.synced_folder ".", "/vagrant", disabled: false
        m.vm.synced_folder "ansible/", "/home/vagrant/ansible-ro",
          create: true,
          mount_options: ["ro"]
      end
    end
  end

  # Provisioning per la VM "ansible"
  config.vm.define "ansible", primary: true do |ansible|
    # --- Blocco root: pacchetti di sistema
    ansible.vm.provision "shell", privileged: true, inline: <<-SHELL
      set -euo pipefail
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y
      apt-get install -y python3-pip git
    SHELL

    # --- Blocco utente vagrant: ansible + collections + ssh setup
    ansible.vm.provision "shell", privileged: false, inline: <<-'SHELL'
      set -euo pipefail
      export PATH="$HOME/.local/bin:$PATH"

      # Ansible per l'utente vagrant
      python3 -m pip install --user 'ansible==9.7.0'
      # Client Python per Kubernetes usato da kubernetes.core
      python3 -m pip install --user 'kubernetes>=29.0.0'

      # Collections da requirements.yml SE presente
      if [ -f /home/vagrant/ansible-ro/requirements.yml ]; then
        ansible-galaxy collection install -r /home/vagrant/ansible-ro/requirements.yml
      else
        echo "[INFO] /home/vagrant/ansible-ro/requirements.yml non trovato: salto install collections"
      fi

      # SSH keys dai private_key Vagrant montati in /vagrant/.vagrant
      mkdir -p /home/vagrant/.ssh
      chmod 700 /home/vagrant/.ssh
      for vm in master worker edge; do
        key_path="/vagrant/.vagrant/machines/$vm/virtualbox/private_key"
        if [ -f "$key_path" ]; then
          cp "$key_path" "/home/vagrant/.ssh/${vm}_key"
          chmod 600 "/home/vagrant/.ssh/${vm}_key"
          echo "Copiata chiave SSH per $vm"
        else
          echo "[WARN] Chiave non trovata per $vm (path: $key_path)"
        fi
      done

      # Usa il tuo ssh_config già versionato nel repo
      cp /home/vagrant/ansible-ro/ssh_config /home/vagrant/.ssh/config
      chmod 600 /home/vagrant/.ssh/config

      # Workspace Ansible (scrivibile)
      mkdir -p /home/vagrant/ansible-work/{logs,cache,tmp,retry}
      cp /home/vagrant/ansible-ro/ansible.cfg /home/vagrant/ansible-work/ansible.cfg
      chmod 644 /home/vagrant/ansible-work/ansible.cfg

      # Aggiungi PATH a .bashrc per sessioni interattive
      if ! grep -q 'export PATH=.*.local/bin' ~/.bashrc; then
        echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
      fi
    SHELL

    # --- Run finale (sempre): attesa SSH + playbook
    ansible.vm.provision "shell", run: "always", privileged: false, inline: <<-'SHELL'
      set -euo pipefail
      export PATH="$HOME/.local/bin:$PATH"
      export ANSIBLE_CONFIG=/home/vagrant/ansible-work/ansible.cfg

      echo "=== Attendo che le VM siano pronte per SSH ==="
      wait_ssh() {
        local host="$1"
        local tries=15
        for i in $(seq 1 $tries); do
          if ssh -o ConnectTimeout=10 -o BatchMode=yes "$host" 'echo OK' >/dev/null 2>&1; then
            echo "$host raggiungibile (tentativo $i)"
            return 0
          fi
          echo "Tentativo $i: $host non raggiungibile, aspetto..."
          sleep 10
        done
        echo "ERRORE: $host non raggiungibile dopo $tries tentativi"
        return 1
      }

      for vm in master worker edge; do
        wait_ssh "$vm"
      done

      echo "=== Eseguo il playbook a fasi ==="
      ansible-playbook /home/vagrant/ansible-ro/phases/00-main-playbook.yml
    SHELL
  end
end
