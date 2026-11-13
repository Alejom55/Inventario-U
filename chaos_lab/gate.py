"""Run a read-only preflight, fixed k6 profile and guarded declarative chaos gate."""

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from .contracts import check_group
from . import lease, providers


def experiment_configuration(environment):
    fields = {
        "toxiproxy_url": "CHAOS_TOXIPROXY_URL", "prometheus_url": "CHAOS_PROMETHEUS_URL",
        "proxy_name": "CHAOS_PROXY_NAME", "expected_upstream": "CHAOS_EXPECTED_UPSTREAM",
        "round": "CHAOS_ROUND", "run_id": "CHAOS_RUN_ID", "lease_db": "CHAOS_LEASE_DB",
        "window_ack": "CHAOS_WINDOW_ACK", "window_start_utc": "CHAOS_WINDOW_START_UTC",
        "window_end_utc": "CHAOS_WINDOW_END_UTC", "max_p95_seconds": "CHAOS_MAX_P95_SECONDS",
    }
    missing = [value for value in fields.values() if not environment.get(value)]
    if missing:
        raise ValueError("Missing experiment configuration: "+", ".join(missing))
    result = {field: environment[name] for field,name in fields.items()}
    if Path(result["lease_db"]).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError("The persistent watchdog database must be outside the checkout")
    providers.validate_scope(result, require_time_remaining=True)
    end = datetime.fromisoformat(result["window_end_utc"].replace("Z", "+00:00"))
    if (end-datetime.now(timezone.utc)).total_seconds() < 240:
        raise ValueError("The fixed load and cleanup need at least four minutes remaining")
    if not lease.ready(result):
        raise ValueError("Server-side watchdog is not ready; no load or fault will start")
    return result


def evaluate_k6(summary, profile, revision, round_name):
    if summary.get("profile") != profile or summary.get("round") != round_name or summary.get("expected_revision") != revision:
        raise ValueError("k6 profile or deployed revision differs from the agreed run")
    metrics = summary["metrics"]
    total = metrics["http_reqs"]["values"]["count"]
    success = metrics["flow_complete"]["values"]["rate"]
    dropped = metrics.get("dropped_iterations", {}).get("values", {}).get("count", 0)
    if not all(isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value) for value in (total,success,dropped)) or total < 0 or dropped < 0 or not 0 <= success <= 1:
        raise ValueError("Invalid or non-finite k6 counters")
    return {"requests": total, "complete_rate": success, "dropped_iterations": dropped,
            "passed": total > 0 and success >= .99 and dropped == 0}


def run(environment=None):
    env = dict(os.environ if environment is None else environment)
    configuration = experiment_configuration(env)
    contracts = check_group(env)
    root = Path(__file__).resolve().parents[1]
    folder = root / "chaos/results" / configuration["run_id"]
    folder.mkdir(parents=True, exist_ok=False)
    profile_path = root / "chaos/load/profile.json"
    profile_bytes = profile_path.read_bytes()
    profile = json.loads(profile_bytes)
    report = {"scope": "Configured group endpoints; infrastructure placement needs separate evidence",
              "round": configuration["round"], "run_id": configuration["run_id"], "revision": env["EXPECTED_APP_REVISION"],
              "profile_sha256": hashlib.sha256(profile_bytes).hexdigest(), "profile": profile,
              "fault": {"type": "outbound-latency", "latency_ms": 1500, "normal_duration_seconds": 60, "watchdog_lease_seconds": 75},
              "threshold": {"max_p95_seconds": float(configuration["max_p95_seconds"]), "minimum_success_rate": .99, "minimum_samples": 100},
              "contracts": contracts, "passed": False, "rollback_verified": False}
    evidence_file = folder / "snapshots.jsonl"
    env["CHAOS_EVIDENCE_FILE"] = str(evidence_file)
    container = "inventario-chaos-load-"+configuration["run_id"]
    arguments = ["docker", "run", "--rm", "--name", container, "--network", "host",
                 "--mount", "type=bind,source="+str(root/"chaos/load")+",target=/load,readonly",
                 "--mount", "type=bind,source="+str(folder)+",target=/work/chaos/results", "-w", "/work"]
    for name in ("CHAOS_TARGET_URL", "CHAOS_ROUND", "CHAOS_RUN_ID", "CHAOS_WINDOW_ACK", "CHAOS_WINDOW_START_UTC", "CHAOS_WINDOW_END_UTC", "TEAM_API_KEY", "SKU_ID", "ALMACEN_ID", "DEPORTISTA_ID", "ARTICULO_ID", "DEPORTBACK_ID_FIELD", "FASTIFY_ID_FIELD", "EXPECTED_APP_REVISION"):
        arguments += ["-e", name]
    arguments += ["grafana/k6:1.3.0@sha256:3ddc8b1a33a2c3d8edc6e99b6a762ae36cba08788463458f5e6a7703e14eb77d", "run", "/load/flow.js"]
    load = None
    started_experiment = False
    try:
        with (folder/"k6.log").open("w", encoding="utf-8") as output:
            load = subprocess.Popen(arguments, env=env, stdout=output, stderr=subprocess.STDOUT)
            start = time.monotonic()
            while time.monotonic()-start < 45:
                if load.poll() is not None:
                    raise RuntimeError("k6 stopped before the steady-state measurement")
                if time.monotonic()-start >= 30:
                    snapshot = providers.flow_snapshot(configuration)
                    if providers.objective_met(snapshot):
                        report["steady_state_measured"] = snapshot
                        break
                time.sleep(2)
            else:
                raise RuntimeError("Measured steady state did not meet the agreed gate")
            started_experiment = True
            report["experiment_started_at_utc"] = datetime.now(timezone.utc).isoformat()
            with (folder/"experiment.log").open("w", encoding="utf-8") as journal_log:
                experiment = subprocess.run([
                    sys.executable, "-m", "chaostoolkit", "--no-version-check", "--no-log-file", "run",
                    "--rollback-strategy", "always", "--journal-path", str(folder/"journal.json"),
                    str(root/"chaos/experiments/outbound-latency.json"),
                ], cwd=root, env=env, stdout=journal_log, stderr=subprocess.STDOUT, timeout=110)
            report["chaos_toolkit_exit_code"] = experiment.returncode
            report["experiment_finished_at_utc"] = datetime.now(timezone.utc).isoformat()
            load_code = load.wait(timeout=max(1, 200-(time.monotonic()-start)))
            report["k6_exit_code"] = load_code
        summaries = json.loads((folder/("k6-"+configuration["round"]+".json")).read_text())
        report["load"] = evaluate_k6(summaries, profile, env["EXPECTED_APP_REVISION"], configuration["round"])
        snapshots = [json.loads(line) for line in evidence_file.read_text().splitlines()]
        fault_samples = [item for item in snapshots if item.get("injected") and item.get("toxic_present")]
        if not fault_samples:
            raise RuntimeError("No metric snapshot was captured while the actual toxic was present")
        report["fault_measurement"] = fault_samples[-1]
        report["fault_events"] = [item for item in snapshots if item.get("event")]
        report["passed"] = experiment.returncode == 0 and load_code == 0 and report["load"]["passed"] and providers.objective_met(fault_samples[-1])
        if not report["passed"]:
            report["failure_reason"] = "Flow objective, complete-response rate, dropped iterations or experiment failed"
    except Exception as error:
        report["failure_reason"] = type(error).__name__+": "+str(error)
        report["passed"] = False
    finally:
        if started_experiment:
            try:
                providers.remove_latency(configuration)
                report["rollback_verified"] = True
                # A removed toxic alone does not prove the three APIs recovered.
                recovery_deadline = time.monotonic()+15
                while True:
                    try:
                        report["recovered_contracts"] = check_group(env)
                        report["recovery_verified"] = True
                        break
                    except Exception:
                        if time.monotonic() >= recovery_deadline:
                            raise RuntimeError("Three-API recovery could not be verified") from None
                        time.sleep(2)
            except Exception as error:
                report["rollback_error"] = type(error).__name__
                report["passed"] = False
        if load is not None and load.poll() is None:
            try:
                stopped = subprocess.run(["docker", "stop", "--time", "5", container], capture_output=True, timeout=15)
                load.wait(timeout=15)
                if stopped.returncode != 0:
                    raise RuntimeError("Load container stop failed")
            except Exception as error:
                report["load_cleanup_error"] = type(error).__name__
                report["passed"] = False
        if profile_bytes != profile_path.read_bytes():
            report["passed"] = False
            report["failure_reason"] = "Load profile changed during the run"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        content = json.dumps(report, indent=2, allow_nan=False)
        for name in ("TEAM_API_KEY", "GRAFANA_PASSWORD"):
            secret = env.get(name, "")
            if secret and secret in content:
                raise RuntimeError("Refusing to write an evidence report containing credentials")
        (folder/"gate-report.json").write_text(content+"\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "rollback_verified": report["rollback_verified"], "report": str(folder/"gate-report.json")}))
    return report["passed"]


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
