"""Rebuild the versioned Grafana dashboard using the standard library."""

import json
from pathlib import Path


def build():
    panels = []
    for index, (title, query, unit) in enumerate([
        ("Peticiones por segundo", 'sum(rate(inventory_http_requests_total{track="TRACK"}[1m]))', "reqps"),
        ("Errores 5xx", 'sum(rate(inventory_http_requests_total{track="TRACK",status=~"5.."}[1m])) / clamp_min(sum(rate(inventory_http_requests_total{track="TRACK"}[1m])),0.001)', "percentunit"),
        ("Errores 4xx", 'sum(rate(inventory_http_requests_total{track="TRACK",status=~"4.."}[1m])) / clamp_min(sum(rate(inventory_http_requests_total{track="TRACK"}[1m])),0.001)', "percentunit"),
        *[(f"Latencia p{p}", f'histogram_quantile({p/100}, sum by (le) (rate(inventory_http_duration_seconds_bucket{{track="TRACK"}}[1m])))', "s") for p in (50, 95, 99)],
        ("CPU sobre limite de un core", 'sum(rate(process_cpu_seconds_total{job="inventory",track="TRACK"}[1m]))', "percentunit"),
        ("Memoria sobre limite de 512 MiB", 'sum(process_resident_memory_bytes{job="inventory",track="TRACK"}) / 536870912', "percentunit"),
        ("Consultas de inventario por segundo", 'sum(rate(inventory_queries_total{track="TRACK"}[1m]))', "reqps"),
    ]):
        for column, track in enumerate(("stable", "canary")):
            panels.append({
                "id": len(panels) + 1, "type": "timeseries", "title": f"{track} | {title}",
                "gridPos": {"x": column * 12, "y": index * 7, "w": 12, "h": 7},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [{"refId": "A", "expr": query.replace("TRACK", track), "legendFormat": track}],
                "fieldConfig": {"defaults": {"unit": unit, "color": {"mode": "fixed", "fixedColor": "blue" if track == "stable" else "orange"}}, "overrides": []},
                "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
            })
    return {
        "uid": "inventory-canary", "title": "Inventario U stable y canary", "schemaVersion": 41,
        "version": 1, "refresh": "5s", "timezone": "browser", "panels": panels,
        "time": {"from": "now-15m", "to": "now"}, "tags": ["canary", "OCI"],
    }


if __name__ == "__main__":
    destination = Path(__file__).parent / "grafana/dashboards/inventory.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
