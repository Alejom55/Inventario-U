provider "oci" {
  region = var.region
}

data "oci_identity_availability_domains" "available" {
  compartment_id = var.tenancy_ocid
}

data "oci_objectstorage_namespace" "account" {
  compartment_id = var.parent_compartment_ocid
}
