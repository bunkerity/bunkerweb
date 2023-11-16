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

# Setup registry
provider "kubernetes" {
  config_path = "/tmp/k8s/kubeconfig"
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