resource "oci_objectstorage_bucket" "api" {
  compartment_id = oci_identity_compartment.project.id
  namespace      = data.oci_objectstorage_namespace.account.namespace
  name           = "${var.project_name}-json"
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"
  versioning     = "Disabled"
}
