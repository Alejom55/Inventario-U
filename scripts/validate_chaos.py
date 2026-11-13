"""Offline syntax and provider validation; never starts an experiment."""

from datetime import datetime, timedelta, timezone
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k6", action="store_true", help="Also inspect the profile using pinned k6 in Docker")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    environment = dict(os.environ)
    fixtures = {
        "CHAOS_TOXIPROXY_URL": "http://127.0.0.1:8474",
        "CHAOS_PROMETHEUS_URL": "http://127.0.0.1:9090",
        "CHAOS_PROXY_NAME": "chaos-deportback",
        "CHAOS_EXPECTED_UPSTREAM": "synthetic.invalid:8000",
        "CHAOS_ROUND": "R0", "CHAOS_RUN_ID": "0" * 32,
        "CHAOS_LEASE_DB": str(Path(__file__).resolve().parents[1] / "chaos/results/offline-validation-only.sqlite3"),
        "CHAOS_WINDOW_ACK": "GROUP_SYNTHETIC_ONLY",
        "CHAOS_WINDOW_START_UTC": now.isoformat(),
        "CHAOS_WINDOW_END_UTC": (now + timedelta(minutes=10)).isoformat(),
        "CHAOS_MAX_P95_SECONDS": "0.5",
        "CHAOS_TARGET_URL": "http://synthetic.invalid",
        "EXPECTED_APP_REVISION": "0"*40,
        "TEAM_API_KEY": "synthetic-inspection-only",
        "SKU_ID": "1", "ALMACEN_ID": "1", "DEPORTISTA_ID": "synthetic", "ARTICULO_ID": "1",
    }
    environment.update(fixtures)
    root = Path(__file__).resolve().parents[1]
    subprocess.run([
        sys.executable, "-m", "chaostoolkit", "--no-version-check", "--no-log-file",
        "validate", "chaos/experiments/outbound-latency.json",
    ], cwd=root, env=environment, check=True)
    if args.k6:
        command = ["docker", "run", "--rm", "--mount",
                   "type=bind,source=" + str(root / "chaos/load") + ",target=/work,readonly",
                   "-w", "/work"]
        for name in fixtures:
            command += ["-e", name]
        command += ["grafana/k6:1.3.0@sha256:3ddc8b1a33a2c3d8edc6e99b6a762ae36cba08788463458f5e6a7703e14eb77d",
                    "inspect", "--include-system-env-vars", "--execution-requirements", "flow.js"]
        subprocess.run(command, cwd=root, env=environment, check=True)


if __name__ == "__main__":
    main()
