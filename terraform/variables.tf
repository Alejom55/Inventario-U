variable "tenancy_ocid" {
  description = "OCID de la tenancy; no es su nombre visible."
  type        = string
  validation {
    condition     = startswith(var.tenancy_ocid, "ocid1.tenancy.")
    error_message = "Indica un OCID de tenancy valido."
  }
}

variable "parent_compartment_ocid" {
  description = "Compartimento padre donde crear el entorno aislado."
  type        = string
  validation {
    condition     = can(regex("^ocid1\\.(compartment|tenancy)\\.", var.parent_compartment_ocid))
    error_message = "Indica un OCID de compartment o tenancy."
  }
}

variable "region" {
  description = "Debe ser la home region para optar a Always Free."
  type        = string
  default     = "sa-bogota-1"
}

variable "compute_shape" {
  description = "A1 por defecto. E5 es facturable y requiere autorizacion de presupuesto."
  type        = string
  default     = "VM.Standard.A1.Flex"
  validation {
    condition     = contains(["VM.Standard.A1.Flex", "VM.Standard.E5.Flex"], var.compute_shape)
    error_message = "Usa A1 o E5; E5 requiere presupuesto autorizado."
  }
}

variable "project_name" {
  type    = string
  default = "inventario-u-s3"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,25}$", var.project_name))
    error_message = "Usa de 3 a 26 letras minusculas, numeros o guiones."
  }
}

variable "api_allowed_cidr" {
  description = "Red IPv4 autorizada a acceder a la demo HTTP (por ejemplo tu IP/32)."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.api_allowed_cidr)) && try(tonumber(split("/", var.api_allowed_cidr)[1]) >= 24, false)
    error_message = "Usa un CIDR IPv4 /24 o mas restringido; no se permite acceso mundial."
  }
}

variable "team_api_key" {
  description = "Clave compartida existente, o vacia para generar una. Guardar como secreto."
  type        = string
  sensitive   = true
  default     = ""
  validation {
    condition     = var.team_api_key == "" || can(regex("^[A-Za-z0-9_-]{24,128}$", var.team_api_key))
    error_message = "La clave debe tener 24-128 caracteres alfanumericos, guion o guion bajo."
  }
}

variable "deportback_api_url" {
  description = "URL publica de la API del companero; vacia hasta disponer del servicio."
  type        = string
  default     = ""
  validation {
    condition     = var.deportback_api_url == "" || can(regex("^https://[^[:space:]]+$", var.deportback_api_url))
    error_message = "Usa HTTPS sin espacios, o deja la URL vacia."
  }
}

variable "fastify_api_url" {
  description = "URL publica de la segunda API; vacia hasta disponer del servicio."
  type        = string
  default     = ""
  validation {
    condition     = var.fastify_api_url == "" || can(regex("^https://[^[:space:]]+$", var.fastify_api_url))
    error_message = "Usa HTTPS sin espacios, o deja la URL vacia."
  }
}
