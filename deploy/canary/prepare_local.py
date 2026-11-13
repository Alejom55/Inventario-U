"""Create private demo configuration without touching existing projects or cloud accounts."""

import json
from pathlib import Path
import re
import secrets
import subprocess

from .gateway import render


def main():
    folder = Path(__file__).resolve().parent / "runtime"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "local.env"
    if target.exists():
        raise SystemExit("Local config already exists; reuse it rather than rotating database credentials")
    image = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", "inventario-canary:local"], text=True).strip()
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise ValueError("Build inventario-canary:local first")
    values = {
        "CANARY_IMAGE": image,
        "APP_REVISION": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "POSTGRES_PASSWORD": secrets.token_hex(16), "TEAM_API_KEY": secrets.token_hex(24),
        "GRAFANA_PASSWORD": secrets.token_urlsafe(32),
        "COMPOSE_PROJECT_NAME": "inventario-canary-local",
        "GATEWAY_BIND": "127.0.0.1", "GATEWAY_PORT": "18000", "PROMETHEUS_PORT": "19090",
    }
    target.write_text(''.join(k + '=' + json.dumps(v) + '\n' for k, v in values.items()), encoding="utf-8")
    target.chmod(0o600)
    (folder / "proxy.conf").write_text(render(0, values["TEAM_API_KEY"]), encoding="utf-8", newline="\n")
    print("Local configuration ready; credentials stay in ignored runtime/local.env")


if __name__ == "__main__":
    main()
