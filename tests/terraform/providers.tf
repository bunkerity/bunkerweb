terraform {  
  required_providers {
    scaleway = {
      source = "scaleway/scaleway"
      version = "2.5.0"
    }
  }
}

provider "scaleway" {
  alias = "scaleway"
}
