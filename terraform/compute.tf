data "oci_core_images" "oracle_linux" {
  compartment_id           = var.parent_compartment_ocid
  operating_system         = "Oracle Linux"
  operating_system_version = "9"
  shape                    = var.compute_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "api" {
  compartment_id       = oci_identity_compartment.project.id
  availability_domain  = data.oci_identity_availability_domains.available.availability_domains[0].name
  display_name         = var.project_name
  shape                = var.compute_shape
  preserve_boot_volume = false

  shape_config {
    ocpus         = 1
    memory_in_gbs = 6
  }
  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.oracle_linux.images[0].id
    boot_volume_size_in_gbs = 50
    boot_volume_vpus_per_gb = 10
  }
  create_vnic_details {
    subnet_id        = oci_core_subnet.api.id
    assign_public_ip = true
    hostname_label   = "inventario"
  }
  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }
  agent_config {
    are_all_plugins_disabled = false
    plugins_config {
      name          = "Compute Instance Run Command"
      desired_state = "ENABLED"
    }
  }
  metadata = {
    inventory_config = jsonencode({
      OCI_REGION         = var.region
      OCI_NAMESPACE      = data.oci_objectstorage_namespace.account.namespace
      OCI_BUCKET_NAME    = oci_objectstorage_bucket.api.name
      DATABASE_SECRET_ID = oci_vault_secret.database.id
      TEAM_SECRET_ID     = oci_vault_secret.team.id
      DEPORTBACK_API_URL = var.deportback_api_url
      FASTIFY_API_URL    = var.fastify_api_url
    })
    user_data = base64encode("#cloud-config\n${yamlencode({
      write_files = [
        { path = "/opt/inventario/bootstrap.sh", permissions = "0700", content = file("${path.module}/../deploy/bootstrap.sh") },
        { path = "/opt/inventario/deploy.sh", permissions = "0700", content = file("${path.module}/../deploy/host-deploy.sh") },
        { path = "/etc/sudoers.d/101-inventario-deploy", permissions = "0440", content = "ocarun ALL=(root) NOPASSWD: /opt/inventario/deploy.sh *\n" }
      ]
      runcmd = [["bash", "/opt/inventario/bootstrap.sh"]]
    })}")
  }
  # Nuevas imagenes del catalogo no deben reemplazar una VM con datos.
  lifecycle {
    ignore_changes = [source_details[0].source_id]
  }
  depends_on = [oci_identity_policy.api]
}
