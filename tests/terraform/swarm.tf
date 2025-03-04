# Variables
variable "swarm_ips" {
  type     = list(string)
  nullable = false
  sensitive = true
}
variable "swarm_ips_id" {
  type     = list(string)
  nullable = false
  sensitive = true
}

# Create cicd_bw_swarm SSH key
resource "scaleway_account_ssh_key" "ssh_key" {
    name       = "cicd_bw_swarm"
    public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_swarm private network
resource "scaleway_vpc_private_network" "pn" {
    name = "cicd_bw_swarm"
}

# Create cicd_bw_swarm_[1-3] instances
resource "scaleway_instance_server" "instances" {
  count = 3
  depends_on = [scaleway_account_ssh_key.ssh_key]
  name = "cicd_bw_swarm_${count.index}"
  type = "DEV1-L"
  image = "debian_bookworm"
  # routed_ip_enabled = true
  ip_id = var.swarm_ips_id[count.index]
}

# Attach to PVC
resource "scaleway_instance_private_nic" "nics" {
  count = 3
  server_id = scaleway_instance_server.instances[count.index].id
  private_network_id = scaleway_vpc_private_network.pn.id
}

# Retrieve private IPs
data "scaleway_ipam_ip" "ips" {
  count = 3
  mac_address = scaleway_instance_private_nic.nics[count.index].mac_address
  type = "ipv4"
}

# Create Ansible inventory file
resource "local_sensitive_file" "ansible_inventory" {
  content = templatefile("templates/swarm_inventory.tftpl", {
    public_ips = var.swarm_ips
    local_ips = data.scaleway_ipam_ip.ips[*].address
  })
  filename = "/tmp/swarm_inventory"
}