#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /opt/inventario/source
if [[ -f deploy/canary/install.sh ]]; then
  exec bash deploy/canary/install.sh "$1"
fi
/opt/inventario/sdk/bin/python deploy/runtime_env.py "$1" /opt/inventario/runtime.env
compose=(docker compose --project-name inventario-oci --env-file /opt/inventario/runtime.env -f deploy/compose.oci.yml)
"${compose[@]}" config --quiet
"${compose[@]}" build --pull api
# Never remove postgres_data during a release.
"${compose[@]}" up -d --wait --wait-timeout 240
"${compose[@]}" exec -T api /app/.venv/bin/python - < deploy/smoke.py
printf '%s\n' "$1" > /opt/inventario/deployed-revision
echo "Deployment verified: $1"
