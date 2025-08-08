terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.59.0"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.19.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = "2.36.0"
    }
  }
}