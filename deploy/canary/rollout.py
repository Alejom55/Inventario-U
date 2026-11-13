"""Run on the OCI host: python -m deploy.canary.rollout promote|regression|rollback."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request, urlopen

from .gate import decide, load_policy, snapshot
from .gateway import render
from .load import Load

FOLDER = Path(__file__).resolve().parent


def load_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = json.loads(value).replace("$$", "$") if value.startswith('"') else value
    return values


def distribution(report, percent):
    n = report["public_requests"]
    if n < 500:
        return False
    if any(label.startswith("unavailable:") for label in report["public"]):
        return False
    expected = percent / 100
    actual = report["public_canary_ratio"]
    if percent in (0, 100):
        return actual == expected
    return abs(actual - expected) <= 4 * math.sqrt(expected * (1 - expected) / n) + .01


class Rollout:
    def __init__(self, env_file, evidence, base_url="http://127.0.0.1:8000", prometheus="http://127.0.0.1:9090"):
        self.values = load_env(env_file)
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", self.values.get("CANARY_IMAGE", "")):
            raise ValueError("CANARY_IMAGE must be an immutable local sha256 image ID")
        self.env_file, self.evidence = str(Path(env_file).resolve()), Path(evidence)
        self.project = self.values.get("COMPOSE_PROJECT_NAME", "inventario-oci")
        self.base_url, self.prometheus = base_url.rstrip("/"), prometheus.rstrip("/")
        self.key = self.values["TEAM_API_KEY"]

    def compose(self, *args):
        subprocess.run(["docker", "compose", "--project-name", self.project, "--env-file", self.env_file,
                        "-f", str(FOLDER / "compose.yml"), *args], check=True, capture_output=True, text=True)

    def event(self, kind, **values):
        event = {"at": datetime.now(timezone.utc).isoformat(), "event": kind, **values}
        self.evidence.parent.mkdir(parents=True, exist_ok=True)
        with self.evidence.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
        print(json.dumps(event, ensure_ascii=False, allow_nan=False), flush=True)

    def stage(self, percent):
        target = FOLDER / "runtime/proxy.conf"
        content = render(percent, self.key)
        previous = target.read_text() if target.exists() else None
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(content.encode("utf-8"))
        temporary.replace(target)
        try:
            self.compose("exec", "-T", "gateway", "nginx", "-t")
            self.compose("exec", "-T", "gateway", "nginx", "-s", "reload")
        except Exception:
            if previous is not None:
                temporary.write_bytes(previous.encode("utf-8"))
                temporary.replace(target)
            raise
        # New workers must be serving before the stage sample starts.
        time.sleep(2)
        self.event("stage", percent=percent)

    def fault(self, rate=0, latency=0):
        request = Request(self.base_url + "/api/v3/admin/fault", method="POST",
                          data=json.dumps({"error_rate": rate, "latency_ms": latency}).encode(),
                          headers={"X-Api-Key": self.key, "Content-Type": "application/json"})
        with urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("Fault switch not acknowledged")

    def verify_rollback(self):
        for _ in range(30):
            request = Request(self.base_url + "/api/live/inventario/query", method="QUERY", data=b"{}",
                              headers={"X-Api-Key": self.key, "Content-Type": "application/json"})
            with urlopen(request, timeout=5) as response:
                if response.status != 200 or response.headers.get("X-App-Track") != "stable":
                    raise RuntimeError("Rollback verification failed")
        self.event("rollback_verified", percent=0, stable_requests=30)

    def rollback(self):
        self.stage(0)
        self.verify_rollback()

    def run(self, scenario, rps=80):
        policy = load_policy()
        self.event("start", scenario=scenario, policy=policy, image=self.values["CANARY_IMAGE"],
                   revision=self.values["APP_REVISION"])
        if scenario == "rollback":
            self.rollback()
            return
        aborted = False
        try:
            self.stage(0)
            self.fault()
            with Load(self.base_url, self.key, rps=rps) as load:
                for stage in policy["stages"]:
                    percent = stage["percent"]
                    self.stage(percent)
                    load.reset(percent)
                    start = time.monotonic()
                    injected = False
                    while True:
                        time.sleep(10)
                        elapsed = time.monotonic() - start
                        if scenario == "regression" and percent == 10 and elapsed >= 20 and not injected:
                            self.fault(rate=.5)
                            self.event("fault_enabled", error_rate=.5)
                            injected = True
                        stable = snapshot(self.prometheus, "stable", policy["window_seconds"])
                        canary = snapshot(self.prometheus, "canary", policy["window_seconds"])
                        action, reasons = decide(stable, canary, policy, elapsed, stage["bake_seconds"])
                        traffic = load.report()
                        if action == "promote" and not distribution(traffic, percent):
                            action, reasons = "pause", ["public traffic distribution or sample invalid"]
                        self.event("analysis", percent=percent, elapsed=round(elapsed, 1), decision=action,
                                   reasons=reasons, stable=stable, canary=canary, traffic=traffic)
                        if action == "abort":
                            self.rollback()
                            aborted = True
                            if scenario != "regression" or not injected:
                                raise RuntimeError("Unexpected SLO violation")
                            return
                        if action == "promote":
                            break
                        if elapsed >= stage["timeout_seconds"]:
                            raise TimeoutError("Stage timed out without enough healthy evidence")
                if scenario == "regression":
                    raise RuntimeError("Injected regression was not detected")
                self.event("promoted", percent=100)
        except BaseException:
            if not aborted:
                self.rollback()
            raise
        finally:
            # Failure reset cannot silently turn an unsuccessful demo into success.
            self.fault()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["promote", "regression", "rollback"])
    parser.add_argument("--env-file", default="/opt/inventario/canary.env")
    parser.add_argument("--evidence", default=str(FOLDER / "evidence/rollout.jsonl"))
    parser.add_argument("--rps", type=int, default=80)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    args = parser.parse_args()
    # One controller at a time; lock is released even on failure.
    with (FOLDER / "runtime/rollout.lock").open("a+") as lock:
        if os.name == "nt":
            import msvcrt
            lock.write("0")
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Rollout(args.env_file, args.evidence, args.base_url, args.prometheus).run(args.scenario, args.rps)


if __name__ == "__main__":
    main()
