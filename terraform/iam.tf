resource "oci_identity_dynamic_group" "api" {
  compartment_id = var.tenancy_ocid
  name           = "${var.project_name}-instances"
  description    = "Solo instancias del compartimento dedicado a esta entrega"
  matching_rule  = "ALL {instance.compartment.id = '${oci_identity_compartment.project.id}'}"
}

resource "oci_identity_policy" "api" {
  compartment_id = oci_identity_compartment.project.id
  name           = "${var.project_name}-runtime"
  description    = "Acceso a los dos secretos, bucket de la API y Run Command propio"
  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.api.name} to manage objects in compartment id ${oci_identity_compartment.project.id} where all {target.bucket.name='${oci_objectstorage_bucket.api.name}', any {request.permission='OBJECT_INSPECT', request.permission='OBJECT_CREATE', request.permission='OBJECT_OVERWRITE', request.permission='OBJECT_READ'}}",
    "Allow dynamic-group ${oci_identity_dynamic_group.api.name} to read secret-bundles in compartment id ${oci_identity_compartment.project.id} where any {target.secret.id='${oci_vault_secret.database.id}', target.secret.id='${oci_vault_secret.team.id}'}",
    "Allow dynamic-group ${oci_identity_dynamic_group.api.name} to use instance-agent-command-execution-family in compartment id ${oci_identity_compartment.project.id} where request.instance.id=target.instance.id"
  ]
}
