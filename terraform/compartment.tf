resource "oci_identity_compartment" "project" {
  compartment_id = var.parent_compartment_ocid
  name           = var.project_name
  description    = "Seguimiento 3: API v2, PostgreSQL e infraestructura Terraform"
  enable_delete  = true
}
