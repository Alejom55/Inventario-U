mock_provider "oci" {
  mock_data "oci_identity_availability_domains" {
    defaults = {
      availability_domains = [{ name = "test:BOG-AD-1" }]
    }
  }
  mock_data "oci_core_images" {
    defaults = {
      images = [{ id = "ocid1.image.oc1.test" }]
    }
  }
  mock_data "oci_objectstorage_namespace" {
    defaults = { namespace = "testnamespace" }
  }
}
mock_provider "random" {}

variables {
  tenancy_ocid            = "ocid1.tenancy.oc1..test"
  parent_compartment_ocid = "ocid1.tenancy.oc1..test"
  api_allowed_cidr        = "203.0.113.10/32"
  compute_shape           = "VM.Standard.A1.Flex"
}

run "small_private_infrastructure" {
  command = apply
  assert {
    condition     = oci_core_instance.api.shape == "VM.Standard.A1.Flex" && oci_core_instance.api.shape_config[0].ocpus == 1 && oci_core_instance.api.shape_config[0].memory_in_gbs == 6
    error_message = "La VM debe conservar la configuracion reducida Always Free."
  }
  assert {
    condition     = tonumber(oci_core_instance.api.source_details[0].boot_volume_size_in_gbs) == 50
    error_message = "No incrementar almacenamiento silenciosamente."
  }
  assert {
    condition     = oci_objectstorage_bucket.api.access_type == "NoPublicAccess"
    error_message = "El bucket no debe ser publico."
  }
  assert {
    condition     = oci_kms_vault.project.vault_type == "DEFAULT" && oci_kms_key.secrets.protection_mode == "SOFTWARE"
    error_message = "No usar Virtual Private Vault ni clave HSM de pago."
  }
  assert {
    condition     = length(oci_core_security_list.api.ingress_security_rules) == 1 && one(oci_core_security_list.api.ingress_security_rules).tcp_options[0].min == 8000
    error_message = "Solo permitir el puerto API; no SSH ni PostgreSQL."
  }
  assert {
    condition     = !strcontains(oci_core_instance.api.metadata["inventory_config"], "POSTGRES_PASSWORD")
    error_message = "Los metadatos no deben incluir contrasenas."
  }
}

run "reject_public_access" {
  command = plan
  variables { api_allowed_cidr = "0.0.0.0/0" }
  expect_failures = [var.api_allowed_cidr]
}

run "explicit_e5_uses_compatible_image" {
  command = plan
  variables { compute_shape = "VM.Standard.E5.Flex" }
  assert {
    condition     = oci_core_instance.api.shape == "VM.Standard.E5.Flex" && data.oci_core_images.oracle_linux.shape == oci_core_instance.api.shape
    error_message = "La imagen debe corresponder a la arquitectura de la VM elegida."
  }
}

run "reject_weak_shared_key" {
  command = plan
  variables { team_api_key = "123" }
  expect_failures = [var.team_api_key]
}

run "reject_http_integration" {
  command = plan
  variables { fastify_api_url = "http://example.org" }
  expect_failures = [var.fastify_api_url]
}
