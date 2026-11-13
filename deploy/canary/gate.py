"""Fail-closed SLO decisions from comparable track snapshots."""

import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def load_policy():
    return json.loads(Path(__file__).with_name("policy.json").read_text())


def snapshot(base_url, track, window=60):
    selector = f'track="{track}"'
    total = f'sum(increase(inventory_http_requests_total{{{selector}}}[{window}s]))'
    queries = {
        "requests": total,
        "5xx": f'sum(increase(inventory_http_requests_total{{{selector},status=~"5.."}}[{window}s])) or vector(0)',
        "4xx": f'sum(increase(inventory_http_requests_total{{{selector},status=~"4.."}}[{window}s])) or vector(0)',
        "business": f'sum(increase(inventory_queries_total{{{selector}}}[{window}s])) or vector(0)',
        "cpu": f'sum(rate(process_cpu_seconds_total{{job="inventory",{selector}}}[{window}s]))',
        "memory": f'sum(process_resident_memory_bytes{{job="inventory",{selector}}})',
        "up": f'min(up{{job="inventory",{selector}}})',
        **{f"p{q}": f'histogram_quantile({q/100}, sum by (le) (rate(inventory_http_duration_seconds_bucket{{{selector}}}[{window}s])))' for q in (50, 95, 99)},
    }
    values = {}
    for name, query in queries.items():
        with urlopen(base_url + "/api/v1/query?" + urlencode({"query": query}), timeout=5) as response:
            body = json.load(response)
        if body.get("status") != "success":
            raise RuntimeError("Prometheus query failed")
        result = body["data"]["result"]
        value = float(result[0]["value"][1]) if len(result) == 1 else float("nan")
        values[name] = value if math.isfinite(value) else None
    return values


def violations(value, policy):
    n = max(value["requests"], 1)
    limits = [
        ("5xx", value["5xx"] / n, policy["maximum_5xx_ratio"]),
        ("4xx", value["4xx"] / n, policy["maximum_4xx_ratio"]),
        ("p95", value["p95"], policy["maximum_p95_seconds"]),
        ("p99", value["p99"], policy["maximum_p99_seconds"]),
        ("cpu", value["cpu"], policy["maximum_cpu_cores"]),
        ("memory", value["memory"], policy["maximum_memory_bytes"]),
    ]
    return [name for name, actual, limit in limits if actual > limit]


def decide(stable, canary, policy, elapsed, bake):
    if canary.get("up") == 0:
        return "abort", ["canary unavailable"]
    if any(v is None for data in (stable, canary) for v in data.values()):
        return "pause", ["missing or non-finite telemetry"]
    if stable["up"] != 1:
        return "pause", ["baseline unavailable"]
    if stable["requests"] < policy["abort_minimum_requests"] or canary["requests"] < policy["abort_minimum_requests"]:
        return "pause", ["collecting initial sample"]
    if violations(stable, policy):
        return "pause", ["unhealthy baseline"]
    reasons = violations(canary, policy)
    if canary["5xx"] / canary["requests"] > stable["5xx"] / stable["requests"] + policy["maximum_error_delta"]:
        reasons.append("5xx regression against baseline")
    if canary["p95"] > stable["p95"] * policy["maximum_p95_ratio"] + policy["p95_tolerance_seconds"]:
        reasons.append("p95 regression against baseline")
    if reasons:
        return "abort", reasons
    if elapsed < bake or min(stable["requests"], canary["requests"]) < policy["minimum_requests"]:
        return "pause", ["bake time or minimum sample incomplete"]
    if min(data["business"] / data["requests"] for data in (stable, canary)) < policy["minimum_business_success_ratio"]:
        return "pause", ["business sample incomplete"]
    return "promote", ["SLO and comparable samples passed"]
