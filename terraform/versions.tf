terraform {
  required_version = "~> 1.16.0"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }

  backend "oci" {
    key = "inventario-u/terraform.tfstate"
  }
}
