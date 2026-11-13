"""Local Docker transport/rollback check, not an R0/R1 or multi-cloud experiment."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import queue
import threading
from urllib.request import urlopen
from uuid import uuid4

from chaos_lab.providers import inject_latency, remove_latency, request_json
from chaos_lab import lease


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
    watchdog = None
    controller = None
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
            "lease_db": str((Path("chaos/results") / (identity + ".sqlite3")).resolve()),
        }
        guard_environment = dict(os.environ)
        guard_environment.update({
            "CHAOS_TOXIPROXY_URL": control, "CHAOS_PROXY_NAME": configuration["proxy_name"],
            "CHAOS_EXPECTED_UPSTREAM": upstream, "CHAOS_LEASE_DB": configuration["lease_db"],
        })
        watchdog = subprocess.Popen([sys.executable, "-m", "chaos_lab.watchdog"],
                                    env=guard_environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(60):
            if lease.ready(configuration):
                break
            time.sleep(.1)
        else:
            raise RuntimeError("Independent local watchdog did not become ready")
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
        # Use a short test lease, kill its controller, and leave the separate guard alive.
        crash_configuration = {**configuration, "run_id": uuid4().hex}
        worker_environment = dict(guard_environment)
        worker_environment["LOCAL_CRASH_PROOF_CONFIGURATION"] = json.dumps(crash_configuration)
        program = """
import json,os,time
from unittest.mock import patch
from chaos_lab import lease
from chaos_lab.providers import inject_latency
c=json.loads(os.environ['LOCAL_CRASH_PROOF_CONFIGURATION'])
arm=lease.arm
with patch('chaos_lab.providers.lease.arm', side_effect=lambda current: arm(current,ttl=2)):
    inject_latency(c)
print('armed',flush=True)
time.sleep(120)
"""
        controller = subprocess.Popen([sys.executable, "-u", "-c", program],
                                      env=worker_environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        messages = queue.Queue()
        threading.Thread(target=lambda: messages.put(controller.stdout.readline()), daemon=True).start()
        if messages.get(timeout=15).strip() != "armed":
            raise RuntimeError("Crash proof controller did not arm its test fault")
        controller.terminate()
        controller.wait(timeout=10)
        for _ in range(60):
            state = request_json(control + "/proxies/" + configuration["proxy_name"])
            if not state["toxics"]:
                break
            time.sleep(.2)
        else:
            raise RuntimeError("Watchdog did not remove the dead controller's fault")
        read()
        result = {
            "scope": "Local Docker with a static nginx fixture; not three cloud APIs or a formal R0/R1 load run",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "toxiproxy_version": version, "baseline_seconds": before,
            "injected_seconds": during, "after_rollback_seconds": after,
            "rollback_verified": True,
            "controller_terminated": True, "autonomous_rollback_verified": True,
            "test_crash_lease_seconds": 2,
        }
        destination = Path("chaos/results/toxiproxy-local-proof.json")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        for process in (controller, watchdog):
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
        for name in reversed(created_containers):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
        if created_network:
            subprocess.run(["docker", "network", "rm", network], capture_output=True, timeout=30)


if __name__ == "__main__":
    main()
