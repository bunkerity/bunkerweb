# Variables
variable "k8s_ip" {
  type     = string
  nullable = false
  sensitive = true
}
# Create cicd_bw_k8s private network
resource "scaleway_vpc_private_network" "pn" {
    name = "cicd_bw_k8s"
}
# Create k8s cluster
resource "scaleway_k8s_cluster" "cluster" {
  type = "kapsule"
  name = "bw_k8s"
  version = "1.28.6"
  cni = "cilium"
  private_network_id = scaleway_vpc_private_network.pn.id
  delete_additional_resources = true
}
# Create k8s pool
resource "scaleway_k8s_pool" "pool" {
  cluster_id = scaleway_k8s_cluster.cluster.id
  name = "bw_k8s"
  node_type = "DEV1-L"
  size = 3
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
  })
  filename = "/tmp/k8s/lb.yml"
}
resource "kubectl_manifest" "lb" {
  depends_on = [local_sensitive_file.lb_yml]
  yaml_body = local_sensitive_file.lb_yml.content
}