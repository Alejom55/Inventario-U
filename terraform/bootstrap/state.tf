terraform {
  required_version = "~> 1.16.0"
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 7.0"
    }
  }
}

variable "compartment_ocid" {
  type = string
}
variable "region" {
  type    = string
  default = "sa-bogota-1"
}
provider "oci" {
  region = var.region
}
data "oci_objectstorage_namespace" "account" {
  compartment_id = var.compartment_ocid
}
resource "oci_objectstorage_bucket" "state" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.account.namespace
  name           = "inventario-u-tfstate"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Enabled"
  lifecycle {
    prevent_destroy = true
  }
}
output "namespace" {
  value = data.oci_objectstorage_namespace.account.namespace
}
output "bucket" {
  value = oci_objectstorage_bucket.state.name
}
