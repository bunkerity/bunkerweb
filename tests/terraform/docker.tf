# Variables
variable "docker_ip" {
  type     = string
  nullable = false
}
variable "docker_ip_id" {
  type     = string
  nullable = false
}

# Create cicd_bw_docker SSH key
resource "scaleway_account_ssh_key" "ssh_key" {
    name       = "cicd_bw_docker"
    public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_docker instance
resource "scaleway_instance_server" "instance" {
  depends_on = [scaleway_account_ssh_key.ssh_key]
  type = "DEV1-M"
  image = "debian_bullseye"
  ip_id = var.docker_ip_id
  zone = "fr-par-1"
}

# Create Ansible inventory file
resource "local_file" "ansible_inventory" {
  content = templatefile("templates/docker_inventory.tftpl", {
    public_ip = var.docker_ip
  })
  filename = "/tmp/docker_inventory"
}
