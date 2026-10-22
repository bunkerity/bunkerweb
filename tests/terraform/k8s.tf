# Variables
variable "k8s_ip" {
  type     = string
  nullable = false
  sensitive = true
}
# Optional Kapsule region override, set with TF_VAR_k8s_region in CICD_SECRETS (BW-355: fr-par out of stock).
# Unset keeps the provider defaults. When set, k8s_ip must be a Load Balancer IP reserved in "<k8s_region>-1".
variable "k8s_region" {
  type    = string
  default = null
}
locals {
  k8s_zone = var.k8s_region == null ? null : "${var.k8s_region}-1"
}
# Create cicd_bw_k8s private network
resource "scaleway_vpc_private_network" "pn" {
    name = "cicd2_bw_k8s"
    region = var.k8s_region
}
# Create k8s cluster
resource "scaleway_k8s_cluster" "cluster" {
  type = "kapsule"
  name = "bw_k8s_2"
  version = "1.35.0"
  cni = "cilium"
  region = var.k8s_region
  private_network_id = scaleway_vpc_private_network.pn.id
  delete_additional_resources = true
}
# Create k8s pool
resource "scaleway_k8s_pool" "pool" {
  cluster_id = scaleway_k8s_cluster.cluster.id
  name = "bw_k8s_2"
  node_type = "POP2-2C-8G"
  size = 3
  region = var.k8s_region
  zone = local.k8s_zone
  wait_for_pool_ready = true
}
# Get kubeconfig file
resource "local_sensitive_file" "kubeconfig" {
  depends_on = [scaleway_k8s_pool.pool]
  content = scaleway_k8s_cluster.cluster.kubeconfig[0].config_file
  filename = "/tmp/k8s/kubeconfig"
}
provider "kubectl" {
  config_path = "${local_sensitive_file.kubeconfig.filename}"
}
# Setup LB
resource "local_sensitive_file" "lb_yml" {
  depends_on = [local_sensitive_file.kubeconfig]
  content = templatefile("templates/lb.yml.tftpl", {
    lb_ip = var.k8s_ip
    lb_zone = local.k8s_zone == null ? "" : local.k8s_zone
  })
  filename = "/tmp/k8s/lb.yml"
}
resource "kubectl_manifest" "lb" {
  depends_on = [local_sensitive_file.lb_yml]
  yaml_body = local_sensitive_file.lb_yml.content
}
