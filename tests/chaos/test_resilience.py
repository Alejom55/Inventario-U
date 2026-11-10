from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.integrations.external_api import ExternalApiError, get_json
from app.integrations.resilience import CircuitBreaker, CircuitOpen, protection


def test_circuit_has_only_one_recovery_probe_and_recovers():
    clock = [0.0]
    breaker = CircuitBreaker(failures=1, cooldown=10, clock=lambda: clock[0])
    breaker.failure(breaker.acquire())
    with pytest.raises(CircuitOpen):
        breaker.acquire()
    clock[0] = 10
    ticket = breaker.acquire()
    assert breaker.state == 0.5
    with ThreadPoolExecutor(max_workers=4) as pool:
        def rejected(_):
            with pytest.raises(CircuitOpen):
                breaker.acquire()
        list(pool.map(rejected, range(8)))
    breaker.success(ticket)
    assert breaker.state == 0


def test_late_response_cannot_close_open_circuit():
    breaker = CircuitBreaker(failures=1)
    old = breaker.acquire()
    breaker.failure(breaker.acquire())
    breaker.success(old)
    assert breaker.state == 1


def test_failed_recovery_probe_reopens_circuit():
    clock = [0.0]
    breaker = CircuitBreaker(failures=1, cooldown=10, clock=lambda: clock[0])
    breaker.failure(breaker.acquire())
    clock[0] = 10
    breaker.failure(breaker.acquire())
    assert breaker.state == 1
    with pytest.raises(CircuitOpen):
        breaker.acquire()


@pytest.mark.parametrize("value", ["nan", "inf", "0", "6", "invalid"])
def test_invalid_dependency_timeouts_fail_closed(monkeypatch, value):
    monkeypatch.setenv("RESILIENCE_MODE", "protected")
    monkeypatch.setenv("DEPORTBACK_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError):
        protection("deportBack", "https://example.test")


def test_baseline_retains_timeout_and_protected_uses_dependency_timeout(monkeypatch):
    assert protection("deportBack", "https://example.test") == (5.0, None)
    monkeypatch.setenv("RESILIENCE_MODE", "protected")
    monkeypatch.setenv("DEPORTBACK_TIMEOUT_SECONDS", "0.25")
    assert protection("deportBack", "https://example.test")[0] == 0.25


def test_repeated_timeouts_open_circuit_and_stop_new_network_calls(monkeypatch):
    monkeypatch.setenv("RESILIENCE_MODE", "protected")
    calls = []
    class Client:
        def __init__(self, timeout):
            calls.append(timeout)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, headers):
            assert headers["X-Trace-Id"] == "trace-demo"
            raise httpx.ReadTimeout("injected latency")
    monkeypatch.setattr("app.integrations.external_api.httpx.Client", Client)
    for _ in range(3):
        with pytest.raises(ExternalApiError, match="tiempo de espera"):
            get_json("https://example.test", "/entity", "deportBack", "trace-demo")
    with pytest.raises(ExternalApiError, match="circuito abierto"):
        get_json("https://example.test", "/entity", "deportBack", "trace-demo")
    assert calls == [0.5, 0.5, 0.5]


def test_client_errors_do_not_open_circuit(monkeypatch):
    monkeypatch.setenv("RESILIENCE_MODE", "protected")
    response = httpx.Response(404, request=httpx.Request("GET", "https://example.test"))
    class Client:
        def __init__(self, timeout):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return response
    monkeypatch.setattr("app.integrations.external_api.httpx.Client", Client)
    for _ in range(4):
        with pytest.raises(ExternalApiError, match="404"):
            get_json("https://example.test", "/entity", "deportBack", "trace")


def test_fault_expires_without_operator_cleanup(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import faults
    monkeypatch.setattr(faults, "TRACK", "canary")
    monkeypatch.setenv("FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("TEAM_API_KEY", "test-key")
    now = [0.0]
    monkeypatch.setattr(faults.time, "monotonic", lambda: now[0])
    api = FastAPI()
    @api.get("/api/v3/skus")
    def skus():
        return []
    faults.install_faults(api)
    client = TestClient(api)
    headers = {"X-Api-Key": "test-key"}
    assert client.post("/api/v3/admin/fault", headers=headers, json={"error_rate": 1, "duration_seconds": 1}).status_code == 200
    assert client.get("/api/v3/skus", headers=headers).status_code == 500
    now[0] = 1
    assert client.get("/api/v3/skus", headers=headers).status_code == 200
