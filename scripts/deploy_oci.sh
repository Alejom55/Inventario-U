#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
terraform -chdir=terraform init -input=false -backend-config=backend.hcl
terraform -chdir=terraform validate
terraform -chdir=terraform plan -out=deploy.tfplan
trap 'rm -f terraform/deploy.tfplan' EXIT
read -r -p 'Aplicar este plan y desplegar la API? Escribe DESPLEGAR: ' confirmation
[[ "$confirmation" == DESPLEGAR ]] || exit 1
terraform -chdir=terraform apply deploy.tfplan
uv run --frozen python scripts/deploy_oci.py \
  --instance-id "$(terraform -chdir=terraform output -raw instance_id)" \
  --compartment-id "$(terraform -chdir=terraform output -raw compartment_id)" \
  --revision "$(git rev-parse HEAD)"
