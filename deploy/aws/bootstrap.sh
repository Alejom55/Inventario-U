#!/bin/bash
set -euo pipefail
umask 077
# Install the independent local deadline before networking or image builds.
cat >/etc/systemd/system/inventario-expiry.service <<'EOF'
[Unit]
Description=End disposable Inventario-U practice
[Service]
Type=oneshot
ExecStart=/usr/sbin/shutdown -h now
EOF
cat >/etc/systemd/system/inventario-expiry.timer <<'EOF'
[Unit]
Description=Authorized Inventario-U deadline
[Timer]
OnCalendar=__DEADLINE__
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now inventario-expiry.timer
dnf install -y docker git
systemctl enable --now docker
install -d /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod 755 /usr/local/lib/docker/cli-plugins/docker-compose
git init /opt/inventario
cd /opt/inventario
git remote add origin https://github.com/Alejom55/Inventario-U.git
git fetch --depth 1 origin '__REVISION__'
git checkout --detach FETCH_HEAD
test "$(git rev-parse HEAD)" = '__REVISION__'
TOKEN=$(curl -fsS -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' http://169.254.169.254/latest/api/token)
INSTANCE=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
PUBLIC_IP=$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4)
export INSTANCE PUBLIC_IP
python3 - <<'PY'
import json, os, secrets
from pathlib import Path
values={name:secrets.token_hex(32) for name in ('TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN','POSTGRES_PASSWORD')}
values.update(APP_REVISION='__REVISION__',AWS_INSTANCE_ID=os.environ['INSTANCE'],PUBLIC_HOST=os.environ['PUBLIC_IP']+'.sslip.io')
folder=Path('deploy/aws')
(folder/'.env').write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
(folder/'runtime').mkdir(mode=0o700,exist_ok=True)
(folder/'runtime/metrics-token').write_text(values['METRICS_BEARER_TOKEN'])
# Prometheus runs as nobody; the parent and .env remain private to root.
(folder/'runtime/metrics-token').chmod(0o644)
(folder/'runtime/credentials.json').write_text(json.dumps(values,indent=2)+'\n')
PY
chmod 644 deploy/aws/prometheus.yml deploy/aws/Caddyfile
docker compose --project-directory deploy/aws --env-file deploy/aws/.env -f deploy/aws/compose.yml up -d --build
for attempt in $(seq 1 90); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
        touch /opt/inventario/BOOTSTRAP_READY
        exit 0
    fi
    sleep 2
done
exit 1
