# Variables
variable "k8s_ip" {
  type     = string
  nullable = false
  sensitive = true
}
variable "k8s_reg_user" {
  type = string
  nullable = false
  sensitive = true
}
variable "k8s_reg_token" {
  type = string
  nullable = false
  sensitive = true
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
  node_type = "DEV1-L"
  size = 3
  wait_for_pool_ready = true
}

# Get kubeconfig file
resource "local_file" "kubeconfig" {
  depends_on = [scaleway_k8s_pool.pool]
  sensitive_content = scaleway_k8s_cluster.cluster.kubeconfig[0].config_file
  filename = "/tmp/k8s/kubeconfig"
}
provider "kubectl" {
  config_path = "${local_file.kubeconfig.filename}"
}

# Setup LB
resource "local_file" "lb_yml" {
  depends_on = [local_file.kubeconfig]
  sensitive_content = templatefile("templates/lb.yml.tftpl", {
    lb_ip = var.k8s_ip
  })
  filename = "/tmp/k8s/lb.yml"
}
resource "kubectl_manifest" "lb" {
  depends_on = [local_file.lb_yml]
  yaml_body = local_file.lb_yml.content
}

# Setup registry
provider "kubernetes" {
  config_path = "${local_file.kubeconfig.filename}"
}
resource "kubernetes_secret" "reg" {
  metadata {
    name = "secret-registry"
  }
  type = "kubernetes.io/dockerconfigjson"
  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        "ghcr.io" = {
          "username" = var.k8s_reg_user
          "password" = var.k8s_reg_token
          "auth"     = base64encode("${var.k8s_reg_user}:${var.k8s_reg_token}")
        }
      }
    })
  }
}