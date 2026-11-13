"""Verify real HTTP contracts; optional seed writes only dedicated demo entities."""

import argparse
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from .rollout import load_env


def request(base_url, key, path, method="GET", body=None, preview=None):
    headers = {"X-Api-Key": key, "Content-Type": "application/json"}
    if preview:
        headers["X-Canary"] = preview
    req = Request(base_url + path, method=method, headers=headers,
                  data=json.dumps(body).encode() if body is not None else None)
    try:
        response = urlopen(req, timeout=5)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        body = json.loads(raw) if raw and "application/json" in response.headers.get("Content-Type", "") else None
        return response.status, response.headers, body


def verify(base_url, key, seed=False):
    for path, preview, track, version in [
        ("/api/v2/health", None, "stable", "2.0.0"),
        ("/api/v3/health", None, "canary", "3.0.0"),
        ("/api/live/health", "true", "canary", "3.0.0"),
        ("/api/live/health", "baseline", "stable", "2.0.0"),
    ]:
        status, headers, body = request(base_url, key, path, preview=preview)
        assert status == 200, (path, status)
        assert headers["X-App-Track"] == track
        assert headers["X-App-Version"] == version
        assert body["version"] == version
    assert request(base_url, "", "/api/v3/health")[0] == 403
    assert request(base_url, "", "/api/live/health", preview="true")[1]["X-App-Track"] == "stable"
    assert request(base_url, key, "/metrics")[0] == 404
    filters = {}
    if seed:
        suffix = uuid4().hex[:12]
        status, _, sku = request(base_url, key, "/api/v2/skus", "POST", {"codigo": "CANARY-" + suffix, "nombre": "Demo canary", "stock_minimo": 10})
        assert status == 201
        status, _, warehouse = request(base_url, key, "/api/v2/almacenes", "POST", {"nombre": "Canary " + suffix, "ubicacion": "Demo aislada"})
        assert status == 201
        filters = {"sku_id": sku["id"], "almacen_id": warehouse["id"]}
        assert request(base_url, key, "/api/v2/movimientos", "POST", {**filters, "tipo": "entrada", "cantidad": 8, "motivo": "Validacion canary"})[0] == 201
    status, _, v2 = request(base_url, key, "/api/v2/inventario/query", "QUERY", filters)
    assert status == 200
    status, _, v3 = request(base_url, key, "/api/v3/inventario/query", "QUERY", filters)
    assert status == 200
    assert len(v2["resultados"]) == len(v3["resultados"])
    for stable, canary in zip(v2["resultados"], v3["resultados"]):
        assert "estado_stock" not in stable
        assert "estado_stock" in canary
        assert all(canary[k] == v for k, v in stable.items())
    if seed:
        assert v3["resultados"][0]["stock_disponible"] == 8
        assert v3["resultados"][0]["estado_stock"] == "bajo"
        assert v3["resultados"][0]["unidades_reponer"] == 2
    print(json.dumps({"smoke": "passed", "tracks": ["stable", "canary"], "filters": filters}))
    return filters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="/opt/inventario/canary.env")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--seed-demo", action="store_true")
    args = parser.parse_args()
    verify(args.base_url, load_env(args.env_file)["TEAM_API_KEY"], args.seed_demo)


if __name__ == "__main__":
    main()
