terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.38.1"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.14.0"
    }
    kubernetes = {
      source = "hashicorp/kubernetes"
      version = "2.26.0"
    }
  }
}