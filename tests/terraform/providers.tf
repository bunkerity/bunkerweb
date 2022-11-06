terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.5.0"
    }
    kubectl = {
      source = "gavinbunney/kubectl"
      version = "1.14.0"
    }
  }
}