# Variables
variable "docker_ip" {
  type     = string
  nullable = false
  sensitive = true
}
variable "docker_ip_id" {
  type     = string
  nullable = false
  sensitive = true
}

# Create cicd_bw_docker SSH key
resource "scaleway_account_ssh_key" "ssh_key" {
    name       = "cicd_bw_docker"
    public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_docker instance
resource "scaleway_instance_server" "instance" {
  depends_on = [scaleway_account_ssh_key.ssh_key]
  name = "cicd_bw_docker"
  type = "DEV1-M"
  image = "debian_bookworm"
  routed_ip_enabled = true
  ip_id = var.docker_ip_id
}

# Create Ansible inventory file
resource "local_sensitive_file" "ansible_inventory" {
  content = templatefile("templates/docker_inventory.tftpl", {
    public_ip = var.docker_ip
  })
  filename = "/tmp/docker_inventory"
}
