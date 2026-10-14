output "instance_id" {
  value = oci_core_instance.api.id
}
output "compartment_id" {
  value = oci_identity_compartment.project.id
}
output "api_url" {
  description = "Demo HTTP restringida al CIDR autorizado; usar solo datos de prueba."
  value       = "http://${oci_core_instance.api.public_ip}:8000"
}
output "bucket_name" {
  value = oci_objectstorage_bucket.api.name
}
output "namespace" {
  value = data.oci_objectstorage_namespace.account.namespace
}
output "team_secret_id" {
  description = "Identificador para consultar la clave en Vault; nunca su contenido."
  value       = oci_vault_secret.team.id
}
