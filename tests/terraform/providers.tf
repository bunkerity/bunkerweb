terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.65.1"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.19.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = "3.0.1"
    }
  }
}