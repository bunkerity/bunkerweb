# Variables
variable "autoconf_ip" {
  type     = string
  nullable = false
  sensitive = true
}
variable "autoconf_ip_id" {
  type     = string
  nullable = false
  sensitive = true
}

# Create cicd_bw_autoconf SSH key
resource "scaleway_account_ssh_key" "ssh_key" {
    name       = "cicd_bw_autoconf"
    public_key = file("~/.ssh/id_rsa.pub")
}

# Create cicd_bw_autoconf instance
resource "scaleway_instance_server" "instance" {
  depends_on = [scaleway_account_ssh_key.ssh_key]
  name = "cicd_bw_autoconf"
  type = "DEV1-M"
  image = "debian_bookworm"
  # routed_ip_enabled = true
  ip_id = var.autoconf_ip_id
}

# Create Ansible inventory file
resource "local_sensitive_file" "ansible_inventory" {
  content = templatefile("templates/autoconf_inventory.tftpl", {
    public_ip = var.autoconf_ip
  })
  filename = "/tmp/autoconf_inventory"
}
