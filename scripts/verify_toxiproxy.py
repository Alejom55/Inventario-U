"""Local Docker transport/rollback check, not an R0/R1 or multi-cloud experiment."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen
from uuid import uuid4

from chaos_lab.providers import inject_latency, remove_latency, request_json


def docker(*arguments):
    return subprocess.check_output(["docker", *arguments], text=True, timeout=180).strip()


def published_port(container, port):
    data = json.loads(docker("inspect", container))[0]
    return data["NetworkSettings"]["Ports"][str(port) + "/tcp"][0]["HostPort"]


def main():
    endpoint = json.loads(docker("context", "inspect"))[0]["Endpoints"]["docker"]["Host"]
    for value in (endpoint, os.getenv("DOCKER_HOST", endpoint)):
        if not value.startswith(("npipe://", "unix://")):
            raise ValueError("This proof only runs on a local Docker daemon")
    identity = uuid4().hex
    network = "inventario-chaos-proof-" + identity[:12]
    peer, proxy = network + "-peer", network + "-proxy"
    created_network = False
    created_containers = []
    try:
        docker("network", "create", network)
        created_network = True
        # Track intended names before start so an uncertain CLI result is cleaned.
        created_containers.append(peer)
        docker("run", "-d", "--name", peer, "--network", network, "nginx:1.28-alpine")
        created_containers.append(proxy)
        docker("run", "-d", "--name", proxy, "--network", network,
               "-p", "127.0.0.1::8474", "-p", "127.0.0.1::8666",
               "ghcr.io/shopify/toxiproxy:2.12.0")
        control = "http://127.0.0.1:" + published_port(proxy, 8474)
        target = "http://127.0.0.1:" + published_port(proxy, 8666)
        for _ in range(30):
            try:
                version = request_json(control + "/version")
                break
            except (OSError, ValueError):
                time.sleep(.2)
        else:
            raise RuntimeError("Local Toxiproxy did not become ready")
        upstream = peer + ":80"
        request_json(control + "/proxies", "POST", {
            "name": "chaos-local-proof", "listen": "0.0.0.0:8666",
            "upstream": upstream, "enabled": True,
        })
        now = datetime.now(timezone.utc)
        configuration = {
            "toxiproxy_url": control, "prometheus_url": "http://127.0.0.1:9090",
            "proxy_name": "chaos-local-proof", "expected_upstream": upstream,
            "round": "R0", "run_id": identity,
            "window_ack": "GROUP_SYNTHETIC_ONLY",
            "window_start_utc": (now-timedelta(seconds=1)).isoformat(),
            "window_end_utc": (now+timedelta(minutes=5)).isoformat(),
            "max_p95_seconds": "0.5",
        }
        def read():
            start = time.monotonic()
            with urlopen(target, timeout=10) as response:
                assert response.status == 200
                assert b"nginx" in response.read()
            return time.monotonic()-start
        before = read()
        try:
            inject_latency(configuration)
            during = read()
            assert during >= 1.3, "Expected the real 1500 ms downstream toxic to delay data"
        finally:
            remove_latency(configuration)
        after = read()
        assert after < during, "Latency did not drop after verified cleanup"
        result = {
            "scope": "Local Docker with a static nginx fixture; not three cloud APIs or a formal R0/R1 load run",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "toxiproxy_version": version, "baseline_seconds": before,
            "injected_seconds": during, "after_rollback_seconds": after,
            "rollback_verified": True,
        }
        destination = Path("chaos/results/toxiproxy-local-proof.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for name in reversed(created_containers):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
        if created_network:
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)


if __name__ == "__main__":
    main()
