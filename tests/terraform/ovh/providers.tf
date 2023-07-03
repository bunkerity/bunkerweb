terraform {
  required_version = ">= 0.14.0"
  required_providers {
    openstack = {
      source = "terraform-provider-openstack/openstack"
      version = "~> 1.48.0"
    }
    ovh = {
      source = "ovh/ovh"
      version = ">= 0.13.0"
    }
  }
}

provider "openstack" {
  alias = "openstack"
}

provider "ovh" {
  alias = "ovh"
}

