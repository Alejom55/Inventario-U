#!/usr/bin/env bash
set -euo pipefail
umask 077
if [[ $# -lt 1 || $# -gt 2 || ! $1 =~ ^[a-f0-9]{40}$ ]]; then
  echo 'Expected full Git commit SHA and optional canary action' >&2
  exit 2
fi
revision=$1
action=${2:-install}
case "$action" in install|promote|regression|rollback) ;; *) exit 2 ;; esac
test -f /opt/inventario/bootstrap.ready
exec 9>/opt/inventario/deploy.lock
flock -n 9 || { echo 'Deployment already running' >&2; exit 1; }
cd /opt/inventario
if [[ $action != install ]]; then
  cd source
  test "$(git rev-parse HEAD)" = "$revision"
  test "$(cat /opt/inventario/deployed-revision)" = "$revision"
  exec /opt/inventario/sdk/bin/python -m deploy.canary.rollout "$action"
fi
if [[ ! -d source/.git ]]; then
  git clone --no-checkout https://github.com/Alejom55/Inventario-U.git source
fi
git -C source fetch origin "$revision" --depth=1
git -C source checkout --detach --force "$revision"
test "$(git -C source rev-parse HEAD)" = "$revision"
exec bash /opt/inventario/source/deploy/release.sh "$revision"
