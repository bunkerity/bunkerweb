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
  routed_ip_enabled = true
  ip_id = var.swarm_ips_id[count.index]
  private_network {
    pn_id = scaleway_vpc_private_network.pn.id
  }
}

# Create Ansible inventory file
resource "local_sensitive_file" "ansible_inventory" {
  content = templatefile("templates/swarm_inventory.tftpl", {
    public_ips = var.swarm_ips
    local_ips = scaleway_instance_server.instances.private_ip
  })
  filename = "/tmp/swarm_inventory"
}