# Variables
variable "k8s_ip" {
  type     = string
  nullable = false
}

# Create k8s cluster
resource "scaleway_k8s_cluster" "cluster" {
  type = "kapsule"
  name = "bw_k8s"
  version = "1.24.7"
  cni = "cilium"
}

# Create k8s pool
resource "scaleway_k8s_pool" "pool" {
  cluster_id = scaleway_k8s_cluster.cluster.id
  name = "bw_k8s"
  node_type = "DEV1-M"
  size = 3
  wait_for_pool_ready = true
}

# Get kubeconfig file
resource "local_file" "kubeconfig" {
  content = scaleway_k8s_pool.pool.kubeconfig.config_file
  filename = "/tmp/kubernetes/kubeconfig"
}

# Create lb.yml file
resource "local_file" "lb_yml" {
  content = templatefile("templates/lb.yml.tftpl", {
    lb_ip = var.k8s_ip
  })
  filename = "/tmp/kubernetes/lb.yml"
}
