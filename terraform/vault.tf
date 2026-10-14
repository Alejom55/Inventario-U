resource "oci_kms_vault" "project" {
  compartment_id = oci_identity_compartment.project.id
  display_name   = var.project_name
  vault_type     = "DEFAULT"
}

resource "oci_kms_key" "secrets" {
  compartment_id      = oci_identity_compartment.project.id
  display_name        = "${var.project_name}-secrets"
  management_endpoint = oci_kms_vault.project.management_endpoint
  protection_mode     = "SOFTWARE"
  key_shape {
    algorithm = "AES"
    length    = 32
  }
}

resource "random_password" "team" {
  length  = 40
  special = false
}

resource "oci_vault_secret" "team" {
  compartment_id = oci_identity_compartment.project.id
  vault_id       = oci_kms_vault.project.id
  key_id         = oci_kms_key.secrets.id
  secret_name    = "${var.project_name}-team-api-key"
  secret_content {
    content_type = "BASE64"
    content      = base64encode(var.team_api_key != "" ? var.team_api_key : random_password.team.result)
  }
}
