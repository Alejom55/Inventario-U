"""Expose compatible v3 routes only in the canary process."""

from typing import Annotated
from fastapi import Depends, Query
from fastapi.routing import APIRoute

from .database import get_db
from .telemetry import TRACK


def enrich_inventory(result):
    for row in result["resultados"]:
        stock, minimum = row["stock_disponible"], row["stock_minimo"]
        row["estado_stock"] = "agotado" if stock == 0 else "bajo" if stock <= minimum else "normal"
        row["unidades_reponer"] = max(0, minimum - stock)
    return result


def install_v3(app, query_inventory):
    if TRACK != "canary":
        return
    for route in list(app.routes):
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/v2"):
            continue
        if route.path == "/api/v2/inventario/query" and "QUERY" in route.methods:
            continue
        if route.path == "/api/v2/inventario" and "GET" in route.methods:
            continue
        app.add_api_route(
            route.path.replace("/api/v2", "/api/v3", 1), route.endpoint,
            methods=list(route.methods), status_code=route.status_code,
            response_model=route.response_model, tags=["v3"],
        )

    @app.api_route("/api/v3/inventario/query", methods=["QUERY"], tags=["v3"])
    def query_v3(filtros: dict, db=Depends(get_db)):
        return enrich_inventory(query_inventory(filtros, db))

    @app.get("/api/v3/inventario", tags=["v3"])
    def query_v3_get(sku_id: Annotated[int, Query(gt=0)], almacen_id: Annotated[int, Query(gt=0)], db=Depends(get_db)):
        return enrich_inventory(query_inventory({"sku_id": sku_id, "almacen_id": almacen_id}, db))
