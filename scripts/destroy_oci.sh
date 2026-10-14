#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
terraform -chdir=terraform init -input=false -backend-config=backend.hcl
terraform -chdir=terraform plan -destroy -out=destroy.tfplan
trap 'rm -f terraform/destroy.tfplan' EXIT
echo 'Elimina VM, PostgreSQL y JSON del bucket. Vault tiene borrado diferido.'
read -r -p 'Revisa el plan. Escribe ELIMINAR para borrar esos datos: ' confirmation
[[ "$confirmation" == ELIMINAR ]] || exit 1
uv run --frozen python scripts/cleanup_oci.py \
  --instance-id "$(terraform -chdir=terraform output -raw instance_id)" \
  --compartment-id "$(terraform -chdir=terraform output -raw compartment_id)" \
  --namespace "$(terraform -chdir=terraform output -raw namespace)" \
  --bucket "$(terraform -chdir=terraform output -raw bucket_name)" \
  --confirm "$(terraform -chdir=terraform output -raw bucket_name)"
terraform -chdir=terraform apply destroy.tfplan
