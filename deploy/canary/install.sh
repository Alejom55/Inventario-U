#!/usr/bin/env bash
set -euo pipefail
umask 077
revision=${1:?Expected full Git SHA}
[[ $revision =~ ^[a-f0-9]{40}$ ]] || exit 2
cd /opt/inventario/source
test "$(git rev-parse HEAD)" = "$revision"
exec 9>/opt/inventario/deploy.lock
flock -n 9 || { echo 'Deployment already running' >&2; exit 1; }
/opt/inventario/sdk/bin/python deploy/runtime_env.py "$revision" /opt/inventario/runtime.env

# Build exactly once. Every traffic stage uses this same content-addressed image.
docker build --tag "inventario-api:$revision" .
image=$(docker image inspect --format '{{.Id}}' "inventario-api:$revision")
[[ $image =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2
/opt/inventario/sdk/bin/python - "$image" <<'PY'
import json
import os
from pathlib import Path
import secrets
from deploy.canary.gateway import render
from deploy.canary.rollout import load_env
folder = Path('deploy/canary/runtime')
folder.mkdir(mode=0o700, exist_ok=True)
password_file = Path('/opt/inventario/grafana.password')
if not password_file.exists():
    password_file.write_text(secrets.token_urlsafe(32))
    password_file.chmod(0o600)
values = load_env('/opt/inventario/runtime.env')
values['CANARY_IMAGE'] = __import__('sys').argv[1]
values['GRAFANA_PASSWORD'] = password_file.read_text().strip()
destination = Path('/opt/inventario/canary.env')
destination.write_text(''.join(k + '=' + json.dumps(v.replace('$', '$$')) + '\n' for k, v in values.items()))
destination.chmod(0o600)
# Nginx master reads this file as root before dropping worker privileges.
(folder / 'proxy.conf').write_text(render(0, values['TEAM_API_KEY']))
PY
compose=(docker compose --project-name inventario-oci --env-file /opt/inventario/canary.env -f deploy/canary/compose.yml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --wait --wait-timeout 120 db
mkdir -p /opt/inventario/backups
backup="/opt/inventario/backups/pre-canary-$(date -u +%Y%m%dT%H%M%SZ).sql"
"${compose[@]}" exec -T db pg_dump -U inventario inventario > "$backup"
test -s "$backup"
# Prepare both tracks before releasing the existing single-container listener.
"${compose[@]}" up -d --wait --wait-timeout 240 stable canary prometheus grafana
docker compose --project-name inventario-oci --env-file /opt/inventario/runtime.env -f deploy/compose.oci.yml stop api
if ! "${compose[@]}" up -d --wait --wait-timeout 120 gateway; then
  "${compose[@]}" stop gateway
  docker compose --project-name inventario-oci --env-file /opt/inventario/runtime.env -f deploy/compose.oci.yml start api
  exit 1
fi
/opt/inventario/sdk/bin/python -m deploy.canary.rollout rollback
printf '%s\n' "$revision" > /opt/inventario/deployed-revision
echo "Canary installed at public 0 percent; PostgreSQL backup saved."
