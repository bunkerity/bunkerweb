# Variables
variable "swarm_ips" {
  type     = list(string)
  nullable = false
}

# Create cicd_bw_swarm SSH key
resource "openstack_compute_keypair_v2" "ssh_key" {
  provider = openstack.openstack
  name = "cicd_bw_swarm"
  public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_swarm network
resource "ovh_cloud_project_network_private" "network" {
  provider = ovh.ovh
  name = "cicd_bw_swarm"
  regions = ["SBG5"]
  vlan_id = 50
}
resource "ovh_cloud_project_network_private_subnet" "subnet" {
  provider = ovh.ovh
  network_id = ovh_cloud_project_network_private.network.id
  start = "192.168.42.1"
  end = "192.168.42.254"
  network = "192.168.42.0/24"
  region = "SBG5"
  no_gateway = true
}

# Create cicd_bw_swarm_[1-3] instances
resource "openstack_compute_instance_v2" "instances" {
  provider = openstack.openstack
  depends_on = [ovh_cloud_project_network_private_subnet.subnet]
  count = 3
  name = "cicd_bw_swarm_${count.index}"
  image_name = "Debian 11"
  flavor_name = "d2-8"
  region = "SBG5"
  key_pair = openstack_compute_keypair_v2.ssh_key.name
  network {
    name = "Ext-Net"
  }
  network {
    name = ovh_cloud_project_network_private.network.name
  }
}

# Attach failover IPs to cicd_bw_swarm_[1-3] instances
#resource "ovh_cloud_project_failover_ip_attach" "failover_ip" {
#  provider = ovh.ovh
#  count = 3
#  ip = var.swarm_ips[${count.index}]
#  routed_to = openstack_compute_instance_v2.instances[${count.index}]
#}

# Create Ansible inventory file
resource "local_file" "ansible_inventory" {
  content = templatefile("templates/swarm_inventory.tftpl", {
    instances = openstack_compute_instance_v2.instances,
    failover_ips = var.swarm_ips
  })
  filename = "/tmp/swarm_inventory"
}
