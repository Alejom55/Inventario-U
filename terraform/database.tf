# PostgreSQL 16 se instala con deploy/compose.oci.yml en Compute.
# El volumen Docker persiste entre releases; destroy elimina la VM y sus datos.
resource "random_password" "database" {
  length  = 32
  special = false
}

resource "oci_vault_secret" "database" {
  compartment_id = oci_identity_compartment.project.id
  vault_id       = oci_kms_vault.project.id
  key_id         = oci_kms_key.secrets.id
  secret_name    = "${var.project_name}-postgres"
  secret_content {
    content_type = "BASE64"
    content      = base64encode(random_password.database.result)
  }
}
