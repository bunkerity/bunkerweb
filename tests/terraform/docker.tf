# Variables
variable "docker_ip" {
  type     = string
  nullable = false
}

# Create cicd_bw_docker SSH key
resource "openstack_compute_keypair_v2" "ssh_key" {
  provider = openstack.openstack
  name = "cicd_bw_docker"
  public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_docker instance
resource "openstack_compute_instance_v2" "instance" {
  provider = openstack.openstack
  name = "cicd_bw_docker"
  image_name = "Debian 11"
  flavor_name = "d2-8"
  region = "SBG5"
  key_pair = openstack_compute_keypair_v2.ssh_key.name
  network {
    name = "Ext-Net"
  }
}

# Attach failover IP to cicd_bw_docker instance
#resource "ovh_cloud_project_failover_ip_attach" "failover_ip" {
#  provider = ovh.ovh
#  ip = var.docker_ip
#  routed_to = openstack_compute_instance_v2.instance.name
#}

# Create Ansible inventory file
resource "local_file" "ansible_inventory" {
  content = templatefile("templates/docker_inventory.tftpl", {
    public_ip = openstack_compute_instance_v2.instance.access_ip_v4,
    failover_ip = var.docker_ip
  })
  filename = "/tmp/docker_inventory"
}
