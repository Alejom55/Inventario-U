#!/usr/bin/env bash
set -euo pipefail
umask 077
dnf install -y dnf-plugins-core git python3-pip
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y --allowerasing docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
python3 -m venv /opt/inventario/sdk
/opt/inventario/sdk/bin/pip install --disable-pip-version-check 'oci==2.187.0'
visudo -cf /etc/sudoers.d/101-inventario-deploy
if systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port=8000/tcp
  firewall-cmd --reload
fi
touch /opt/inventario/bootstrap.ready
