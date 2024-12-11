terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.44.0"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.18.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = "2.32.0"
    }
  }
}