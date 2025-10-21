# Vagrantfile for the 5G Kubernetes Testbed
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

  # Provisioning for the "ansible" VM
  config.vm.define "ansible", primary: true do |ansible|
    # --- Root block: system packages
    ansible.vm.provision "shell", privileged: true, inline: <<-SHELL
      set -euo pipefail
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y
      apt-get install -y python3-pip git
    SHELL

    # --- User vagrant block: ansible + collections + ssh setup
    ansible.vm.provision "shell", privileged: false, inline: <<-'SHELL'
      set -euo pipefail
      export PATH="$HOME/.local/bin:$PATH"

      # Ansible for the vagrant user
      python3 -m pip install --user 'ansible==9.7.0'
      # Client Python for Kubernetes used by kubernetes.core
      python3 -m pip install --user 'kubernetes>=29.0.0'

      # Collections from requirements.yml if present
      if [ -f /home/vagrant/ansible-ro/requirements.yml ]; then
        ansible-galaxy collection install -r /home/vagrant/ansible-ro/requirements.yml
      else
        echo "[INFO] /home/vagrant/ansible-ro/requirements.yml not found: skipping collections installation"
      fi

      # SSH keys from private_key Vagrant mounted in /vagrant/.vagrant
      mkdir -p /home/vagrant/.ssh
      chmod 700 /home/vagrant/.ssh
      for vm in master worker edge; do
        key_path="/vagrant/.vagrant/machines/$vm/virtualbox/private_key"
        if [ -f "$key_path" ]; then
          cp "$key_path" "/home/vagrant/.ssh/${vm}_key"
          chmod 600 "/home/vagrant/.ssh/${vm}_key"
          echo "Copied SSH key for $vm to /home/vagrant/.ssh/${vm}_key"
        else
          echo "[WARN] Key not found for $vm (path: $key_path)"
        fi
      done

      # Use ssh_config already versioned in the repo
      cp /home/vagrant/ansible-ro/ssh_config /home/vagrant/.ssh/config
      chmod 600 /home/vagrant/.ssh/config

      # Workspace Ansible (writable)
      mkdir -p /home/vagrant/ansible-work/{logs,cache,tmp,retry}
      cp /home/vagrant/ansible-ro/ansible.cfg /home/vagrant/ansible-work/ansible.cfg
      chmod 644 /home/vagrant/ansible-work/ansible.cfg

      # Add PATH to .bashrc for interactive sessions
      if ! grep -q 'export PATH=.*.local/bin' ~/.bashrc; then
        echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
      fi
    SHELL

    # --- Final run (always): wait for SSH + timed playbook execution

    ansible.vm.provision "shell", run: "always", privileged: false, inline: <<-'SHELL'
      set -euo pipefail
      export PATH="$HOME/.local/bin:$PATH"
      export ANSIBLE_CONFIG=/home/vagrant/ansible-work/ansible.cfg

      t0=$(date +%s)

      echo "=== Waiting for SSH on VMs ==="
      wait_ssh() {
        local host="$1" tries=15
        for i in $(seq 1 $tries); do
          if ssh -o ConnectTimeout=10 -o BatchMode=yes "$host" 'echo OK' >/dev/null 2>&1; then
            echo "$host reachable (attempt $i)"
            return 0
          fi
          echo "Attempt $i: $host not reachable, retrying..."
          sleep 10
        done
        echo "ERROR: $host not reachable after $tries attempts"
        return 1
      }

      for vm in master worker edge; do wait_ssh "$vm"; done

      echo "=== Running phased playbook (timed) ==="
      pb_t0=$(date +%s)
      ansible-playbook /home/vagrant/ansible-ro/phases/00-main-playbook.yml
      pb_t1=$(date +%s)

      t1=$(date +%s)

      echo "=== Timing summary ==="
      echo "Playbook runtime: $((pb_t1 - pb_t0)) seconds"
      echo "Provisioning (this script): $((t1 - t0)) seconds"

      # Optional: store timings for later use
      mkdir -p /home/vagrant/ansible-work/logs
      {
        echo "playbook_seconds=$((pb_t1 - pb_t0))"
        echo "provision_seconds=$((t1 - t0))"
      } > /home/vagrant/ansible-work/logs/provision.timings
    SHELL

  end
end
