import io
import json

import pytest

from deploy.canary import gate


HEALTHY = {"requests": 1500, "5xx": 0, "4xx": 0, "business": 1500,
           "p50": .02, "p95": .1, "p99": .2, "cpu": .2, "memory": 100_000_000, "up": 1}


@pytest.mark.parametrize("change,elapsed,expected", [
    ({}, 120, "promote"), ({}, 30, "pause"),
    ({"requests": 99}, 120, "pause"), ({"requests": 999}, 120, "pause"),
    ({"5xx": 30}, 120, "abort"), ({"4xx": 30}, 120, "abort"),
    ({"p95": .3}, 120, "abort"), ({"p95": .6}, 120, "abort"),
    ({"p99": 1.1}, 120, "abort"), ({"cpu": .9}, 120, "abort"),
    ({"memory": 500_000_000}, 120, "abort"), ({"business": 100}, 120, "pause"),
    ({"p95": None}, 120, "pause"), ({"up": 0}, 120, "abort"),
])
def test_decision(change, elapsed, expected):
    result, reasons = gate.decide(HEALTHY, {**HEALTHY, **change}, gate.load_policy(), elapsed, 120)
    assert result == expected
    assert reasons


def test_bad_baseline_never_promotes_or_blames_canary():
    assert gate.decide({**HEALTHY, "5xx": 100}, HEALTHY, gate.load_policy(), 120, 120)[0] == "pause"


def test_prometheus_missing_nan_and_api_failure(monkeypatch):
    def reply(value):
        return io.BytesIO(json.dumps(value).encode())
    monkeypatch.setattr(gate, "urlopen", lambda *a, **k: reply({"status": "success", "data": {"result": []}}))
    assert all(value is None for value in gate.snapshot("http://prometheus", "canary").values())
    monkeypatch.setattr(gate, "urlopen", lambda *a, **k: reply({"status": "success", "data": {"result": [{"value": [0, "NaN"]}]}}))
    assert all(value is None for value in gate.snapshot("http://prometheus", "canary").values())
    monkeypatch.setattr(gate, "urlopen", lambda *a, **k: reply({"status": "error"}))
    with pytest.raises(RuntimeError):
        gate.snapshot("http://prometheus", "canary")
