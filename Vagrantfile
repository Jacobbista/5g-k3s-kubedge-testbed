# Vagrantfile for the 5G Kubernetes Testbed
#
# DEPLOYMENT MODES:
#   vagrant up                       - Deploy 5G Core only (phases 1-5), DEFAULT
#   DEPLOY_MODE=full vagrant up      - Deploy everything including UERANSIM
#
# After deployment, you can manually run phase 6 (UERANSIM) from ansible VM:
#   vagrant ssh ansible
#   cd ~/ansible-ro && ansible-playbook phases/06-ueransim-mec/playbook.yml -i inventory.ini
#
Vagrant.configure("2") do |config|
  config.ssh.insert_key = true
  config.vm.box_check_update = false
  
  # Deployment mode: "core_only" (default) or "full"
  deploy_mode = ENV['DEPLOY_MODE'] || 'core_only'

  nodes = {
    "master"  => { cpu: 4, mem: 4096, ip: "192.168.56.10", box: "ubuntu/jammy64" },
    "worker"  => { cpu: 8, mem: 8192, ip: "192.168.56.11", box: "ubuntu/jammy64" },
    "edge"    => { cpu: 4, mem: 4096, ip: "192.168.56.12", box: "ubuntu/jammy64" },
    "ansible" => { cpu: 2, mem: 1024, ip: "192.168.56.13", box: "ubuntu/jammy64" }
  }

  # Secondary network for physical RAN connection (worker only)
  # Bridged to host physical NIC for femtocell / external gNB connectivity
  # Set PHYSICAL_RAN_BRIDGE env var to your NIC name, or edit below
  # NOTE: Worker gets .1 (bridge role), AMF pod gets .150 via macvlan NAD
  ran_network = {
    "worker" => { 
      ip: "192.168.5.1", 
      netmask: "255.255.255.0", 
      bridge: ENV['PHYSICAL_RAN_BRIDGE'] || "enx00e04c6817b7"
    }
  }

  nodes.each do |name, spec|
    config.vm.define name, primary: (name == "ansible") do |m|
      m.vm.hostname = name
      m.vm.network "private_network", ip: spec[:ip]
      m.vm.box = spec[:box]
      
      # Add bridged RAN network interface for worker (for physical femtocell)
      if ran_network.key?(name)
        m.vm.network "public_network", 
          ip: ran_network[name][:ip],
          netmask: ran_network[name][:netmask],
          bridge: ran_network[name][:bridge],
          use_dhcp_assigned_default_route: false
      end

      m.vm.provider "virtualbox" do |vb|
        vb.cpus   = spec[:cpu]
        vb.memory = spec[:mem]
        vb.name = "#{name}-5g-k8s-testbed"
        
        # Enable promiscuous mode on RAN interface for OVS bridging
        if ran_network.key?(name)
          vb.customize ["modifyvm", :id, "--nicpromisc3", "allow-all"]
        end
      end

      # VM time sync with host (requires Guest Additions; reduces clock drift)
      m.trigger.after [:up, :resume, :reload] do |t|
        t.name = "Enable VM time sync (#{name})"
        t.run = {
          inline: "VBoxManage guestproperty set \"#{name}-5g-k8s-testbed\" \"/VirtualBox/GuestAdd/VBoxService/--timesync-interval\" \"10000\" 2>/dev/null || true"
        }
      end

      # Enable promiscuous mode on RAN interface for macvlan to work properly
      # Uses trigger instead of provisioner to run on both 'up' and 'resume'
      if ran_network.key?(name)
        m.trigger.after [:up, :resume, :reload] do |t|
          t.name = "Enable promiscuous mode on #{name}"
          t.run = {
            inline: "vagrant ssh #{name} -c 'sudo ip link set enp0s9 promisc on && echo Promiscuous mode enabled on enp0s9'"
          }
        end
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

      # Ensure interactive sessions use writable Ansible config.
      # This avoids ansible.cfg auto-discovery issues in world-writable synced folders.
      if ! grep -q 'export ANSIBLE_CONFIG=/home/vagrant/ansible-work/ansible.cfg' ~/.bashrc; then
        echo 'export ANSIBLE_CONFIG=/home/vagrant/ansible-work/ansible.cfg' >> ~/.bashrc
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
      echo "DEPLOY_MODE: #{deploy_mode}"
      pb_t0=$(date +%s)
      
      if [ "#{deploy_mode}" = "full" ]; then
        echo "🚀 Full deployment mode: including UERANSIM (phase 6)"
        ansible-playbook /home/vagrant/ansible-ro/phases/00-main-playbook.yml
      else
        echo "🔧 Core-only mode (default): deploying phases 1-5"
        echo "   To add UERANSIM later, run from ansible VM:"
        echo "   cd ~/ansible-ro && ansible-playbook phases/06-ueransim-mec/playbook.yml -i inventory.ini"
        ansible-playbook /home/vagrant/ansible-ro/phases/00-main-playbook.yml --skip-tags phase6,ueransim,mec
      fi
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
