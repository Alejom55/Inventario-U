from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import canary
from app.database import get_db
from app.main import app


def test_stable_identity_on_success_auth_and_missing_route(monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "test-secret")
    for name in ("crear_tabla_skus", "crear_tabla_almacenes", "crear_tabla_movimientos"):
        monkeypatch.setattr("app.main." + name, lambda: None)
    with TestClient(app, raise_server_exceptions=False) as client:
        for path, code in [("/health", 200), ("/api/v2/skus", 401), ("/unknown", 404)]:
            response = client.get(path)
            assert response.status_code == code
            assert response.headers["X-App-Version"] == "2.0.0"
            assert response.headers["X-App-Track"] == "stable"
            assert "X-App-Revision" in response.headers
        metrics = client.get("/metrics").text
        assert 'inventory_http_requests_total{method="GET"' in metrics


def test_v3_enriches_stock_without_altering_v2(monkeypatch):
    monkeypatch.setattr(canary, "TRACK", "canary")
    api = FastAPI()

    @api.api_route("/api/v2/inventario/query", methods=["QUERY"])
    def query(filtros: dict):
        return {"resultados": [{"stock_disponible": filtros["stock"], "stock_minimo": 5}]}

    canary.install_v3(api, lambda filtros, db: query(filtros))
    api.dependency_overrides[get_db] = lambda: None
    with TestClient(api) as client:
        for stock, state, replenish in [(0, "agotado", 5), (3, "bajo", 2), (5, "bajo", 0), (8, "normal", 0)]:
            response = client.request("QUERY", "/api/v3/inventario/query", json={"stock": stock})
            assert response.status_code == 200
            row = response.json()["resultados"][0]
            assert row["estado_stock"] == state
            assert row["unidades_reponer"] == replenish
        stable = client.request("QUERY", "/api/v2/inventario/query", json={"stock": 3})
        assert "estado_stock" not in stable.json()["resultados"][0]


def test_stable_does_not_register_v3(monkeypatch):
    monkeypatch.setattr(canary, "TRACK", "stable")
    api = FastAPI()
    canary.install_v3(api, None)
    assert not any(route.path.startswith("/api/v3") for route in api.routes)
