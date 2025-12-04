terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.64.0"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.19.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = "2.38.0"
    }
  }
}