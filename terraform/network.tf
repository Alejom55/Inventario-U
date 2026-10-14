resource "oci_core_vcn" "project" {
  compartment_id = oci_identity_compartment.project.id
  cidr_blocks    = ["10.30.0.0/16"]
  display_name   = var.project_name
  dns_label      = "inventario"
}

resource "oci_core_internet_gateway" "project" {
  compartment_id = oci_identity_compartment.project.id
  vcn_id         = oci_core_vcn.project.id
  display_name   = "${var.project_name}-internet"
}

resource "oci_core_route_table" "public" {
  compartment_id = oci_identity_compartment.project.id
  vcn_id         = oci_core_vcn.project.id
  route_rules {
    network_entity_id = oci_core_internet_gateway.project.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }
}

resource "oci_core_security_list" "api" {
  compartment_id = oci_identity_compartment.project.id
  vcn_id         = oci_core_vcn.project.id
  display_name   = "${var.project_name}-api"

  egress_security_rules {
    protocol    = "all"
    destination = "0.0.0.0/0"
  }

  ingress_security_rules {
    protocol = "6"
    source   = var.api_allowed_cidr
    tcp_options {
      min = 8000
      max = 8000
    }
  }
}

resource "oci_core_subnet" "api" {
  compartment_id             = oci_identity_compartment.project.id
  vcn_id                     = oci_core_vcn.project.id
  cidr_block                 = "10.30.1.0/24"
  display_name               = "${var.project_name}-api"
  dns_label                  = "api"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_security_list.api.id]
  prohibit_public_ip_on_vnic = false
}
