import json
import logging

from fastapi.testclient import TestClient
import pytest

from app import main, telemetry
from app.database import get_db
from app.integrations.external_api import ExternalApiError
from app.observability import JsonFormatter, correlation_id


@pytest.fixture
def coordinator(monkeypatch):
    class Database:
        def execute(self, *args):
            return self
        def fetchall(self):
            return [{"sku_id": 1, "almacen_id": 2, "stock_disponible": 8}]
    monkeypatch.setattr(main.app, "dependency_overrides", {get_db: lambda: Database()})
    monkeypatch.setenv("TEAM_API_KEY", "synthetic-team-key")
    monkeypatch.setenv("CHAOS_ROUND", "R0")
    monkeypatch.setenv("RESILIENCE_MODE", "baseline")
    return TestClient(main.app)


def query(client, trace="trace-coordinator"):
    return client.get("/api/v2/integracion", params={"sku_id": 1, "almacen_id": 2, "deportista_id": "synthetic-person", "articulo_id": 7}, headers={"X-Api-Key": "synthetic-team-key", "X-Trace-Id": trace})


def test_calls_are_sequential_and_share_trace(coordinator, monkeypatch):
    calls = []
    def person(identity, trace):
        calls.append(("person", identity, trace))
        return {"id": identity}
    def article(identity, trace):
        assert calls == [("person", "synthetic-person", "trace-coordinator")]
        calls.append(("article", identity, trace))
        return {"id": identity}
    monkeypatch.setattr(main, "obtener_deportista", person)
    monkeypatch.setattr(main, "obtener_articulo", article)
    before = telemetry.FLOWS.labels("R0", "complete")._value.get()
    response = query(coordinator)
    assert response.status_code == 200
    assert response.headers["X-Trace-Id"] == response.json()["trace_id"] == "trace-coordinator"
    assert response.headers["X-Chaos-Round"] == "R0"
    assert response.headers["X-Resilience-Mode"] == "baseline"
    assert telemetry.FLOWS.labels("R0", "complete")._value.get() == before+1
    assert calls[-1] == ("article", 7, "trace-coordinator")


def test_fast_dependency_error_is_not_complete_flow(coordinator, monkeypatch):
    def unavailable(*args):
        raise ExternalApiError("deportBack", "unavailable")
    monkeypatch.setattr(main, "obtener_deportista", unavailable)
    monkeypatch.setattr(main, "obtener_articulo", lambda *args: pytest.fail("Second dependency must not be called"))
    before = telemetry.FLOWS.labels("R0", "error")._value.get()
    response = query(coordinator)
    assert response.status_code == 502
    assert response.headers["X-Trace-Id"] == "trace-coordinator"
    assert telemetry.FLOWS.labels("R0", "error")._value.get() == before+1


def test_malformed_entity_does_not_count_as_success(coordinator, monkeypatch):
    monkeypatch.setattr(main, "obtener_deportista", lambda *args: [])
    response = query(coordinator)
    assert response.status_code == 502
    assert response.json()["detail"]["service"] == "deportBack"


def test_invalid_synthetic_ids_rejected(coordinator):
    response = coordinator.get("/api/v2/integracion", params={"sku_id": 0, "almacen_id": 2, "deportista_id": "../admin", "articulo_id": 7}, headers={"X-Api-Key": "synthetic-team-key"})
    assert response.status_code == 422


@pytest.mark.parametrize("value", [None, "", "x"*129, "trace\nforged", "á"])
def test_invalid_trace_is_replaced_with_bounded_id(value):
    result = correlation_id(value)
    assert len(result) == 36 and "\n" not in result


def test_structured_log_keeps_trace_and_excludes_credentials():
    record = logging.LogRecord("app.integration", logging.INFO, __file__, 1, "Dependency completed", (), None)
    record.trace_id = "trace-json"
    record.service = "deportBack"
    record.api_key = "must-not-appear"
    output = JsonFormatter().format(record)
    assert json.loads(output)["trace_id"] == "trace-json"
    assert "must-not-appear" not in output
