"""Only alter one explicitly selected Toxiproxy proxy in an agreed UTC window."""

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from . import lease

_fault_armed = False


def record_evidence(event):
    path = os.getenv("CHAOS_EVIDENCE_FILE")
    if path:
        with Path(path).open("a", encoding="utf-8") as output:
            output.write(json.dumps({"captured_at_utc": datetime.now(timezone.utc).isoformat(), **event})+"\n")


def request_json(url, method="GET", body=None):
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(url, method=method, data=data, headers=headers), timeout=5) as response:
        content = response.read()
        return json.loads(content) if content else None


def validate_scope(configuration, require_time_remaining=False):
    c = configuration
    if c.get("window_ack") != "GROUP_SYNTHETIC_ONLY":
        raise ValueError("The team must acknowledge its agreed synthetic-data window")
    for field in ("toxiproxy_url", "prometheus_url"):
        url = urlsplit(c[field])
        if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"} or url.username or url.password or url.query or url.fragment:
            raise ValueError("Control and metrics URLs must use private loopback HTTP without credentials")
    if not re.fullmatch(r"chaos-[a-z0-9-]{1,40}", c["proxy_name"]):
        raise ValueError("Only a dedicated chaos-* proxy may be modified")
    if c.get("round") not in {"R0", "R1"}:
        raise ValueError("Round must be R0 or R1")
    if not re.fullmatch(r"[a-f0-9]{32}", c.get("run_id", "")):
        raise ValueError("Every execution needs a fresh 32-character hexadecimal run ID")
    start = datetime.fromisoformat(c["window_start_utc"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(c["window_end_utc"].replace("Z", "+00:00"))
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Window timestamps require a timezone")
    now = datetime.now(timezone.utc)
    if not start <= now < end:
        raise ValueError("Outside the agreed experiment window")
    if require_time_remaining and (end - now).total_seconds() < 90:
        raise ValueError("At least 90 seconds must remain in the window")
    maximum = float(c["max_p95_seconds"])
    if not math.isfinite(maximum) or not 0 < maximum <= 5:
        raise ValueError("Declare a finite p95 objective in (0,5] seconds")


def prometheus_value(expression, configuration):
    data = request_json(configuration["prometheus_url"].rstrip("/") + "/api/v1/query?" + urlencode({"query": expression}))
    if data.get("status") != "success":
        raise ValueError("Prometheus query failed")
    result = data["data"]["result"]
    if len(result) != 1:
        raise ValueError("Missing or ambiguous metric sample")
    value = float(result[0]["value"][1])
    if not math.isfinite(value):
        raise ValueError("Metric must be finite")
    return value


def flow_snapshot(configuration):
    validate_scope(configuration)
    # Scope to the flow under test; inventory-only traffic cannot satisfy this gate.
    selector = 'round="' + configuration["round"] + '"'
    total = prometheus_value('sum(increase(inventory_flow_requests_total{' + selector + '}[30s]))', configuration)
    successes = prometheus_value('sum(increase(inventory_flow_requests_total{' + selector + ',outcome="complete"}[30s])) or vector(0)', configuration)
    p95 = prometheus_value('histogram_quantile(0.95,sum by(le)(rate(inventory_flow_duration_seconds_bucket{' + selector + '}[30s])))', configuration)
    return {"round": configuration["round"], "requests": total, "successes": successes, "success_rate": successes/max(total,1), "p95_seconds": p95, "max_p95_seconds": float(configuration["max_p95_seconds"])}


def objective_met(snapshot):
    # A fast 502 is not a successful business flow. Both conditions must hold.
    return snapshot["requests"] >= 100 and snapshot["success_rate"] >= 0.99 and snapshot["p95_seconds"] <= snapshot["max_p95_seconds"]


def within_objective(configuration=None):
    snapshot = flow_snapshot(configuration)
    snapshot.update({"captured_at_utc": datetime.now(timezone.utc).isoformat(), "run_id": configuration["run_id"], "injected": _fault_armed})
    if _fault_armed:
        state = request_json(proxy_url(configuration))
        snapshot["toxic_present"] = any(item["name"] == "inventario-latency-"+configuration["run_id"] for item in state["toxics"])
    record_evidence(snapshot)
    print(json.dumps(snapshot))
    return objective_met(snapshot) and (not _fault_armed or snapshot.get("toxic_present", False))


def proxy_url(configuration):
    return configuration["toxiproxy_url"].rstrip("/") + "/proxies/" + configuration["proxy_name"]


def inject_latency(configuration=None):
    global _fault_armed
    validate_scope(configuration, require_time_remaining=True)
    url = proxy_url(configuration)
    proxy = request_json(url)
    if proxy["upstream"] != configuration["expected_upstream"] or not proxy["enabled"] or proxy["toxics"]:
        raise ValueError("Proxy must match the agreed upstream, be enabled and have no existing toxics")
    lease.arm(configuration)
    # A downstream toxic delays the companion's response, not unrelated traffic.
    result = request_json(url + "/toxics", "POST", {
        "name": "inventario-latency-" + configuration["run_id"], "type": "latency", "stream": "downstream",
        "toxicity": 1, "attributes": {"latency": 1500, "jitter": 0},
    })
    _fault_armed = True
    record_evidence({"event":"fault_injected","run_id":configuration["run_id"]})
    return result


def remove_latency(configuration=None):
    global _fault_armed
    # Cleanup deliberately does not require a still-open window.
    c = configuration
    control = urlsplit(c["toxiproxy_url"])
    if control.scheme != "http" or control.hostname not in {"127.0.0.1", "localhost", "::1"} or control.username or control.password or control.query or control.fragment:
        raise ValueError("Cleanup requires the same private control endpoint")
    if not re.fullmatch(r"chaos-[a-z0-9-]{1,40}", c["proxy_name"]):
        raise ValueError("Invalid dedicated proxy name")
    if not re.fullmatch(r"[a-f0-9]{32}", c.get("run_id", "")):
        raise ValueError("Invalid run ID")
    url = proxy_url(c)
    if request_json(url)["upstream"] != c["expected_upstream"]:
        raise ValueError("Upstream changed; refusing cleanup on another target")
    toxic_name = "inventario-latency-" + c["run_id"]
    # Even an uncertain POST outcome is cleaned by its deterministic toxic name.
    try:
        request_json(url + "/toxics/" + toxic_name, "DELETE")
    except HTTPError as error:
        if error.code != 404:
            raise
    state = request_json(url)
    if any(toxic["name"] == toxic_name for toxic in state["toxics"]):
        raise RuntimeError("Rollback could not be verified")
    lease.release(c)
    _fault_armed = False
    record_evidence({"event":"rollback_verified","run_id":c["run_id"]})
    return True
