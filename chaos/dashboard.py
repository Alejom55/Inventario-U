"""Build the dedicated R0/R1 dashboard; does not publish or manufacture data."""
import json
from pathlib import Path


def build():
    queries = [
        ("Flujos por segundo", 'sum(rate(inventory_flow_requests_total{round="ROUND"}[30s]))',"reqps"),
        ("Flujos completos", '(sum(rate(inventory_flow_requests_total{round="ROUND",outcome="complete"}[30s])) or vector(0))/clamp_min(sum(rate(inventory_flow_requests_total{round="ROUND"}[30s])),0.001)',"percentunit"),
        ("Latencia E2E p95 (incluye errores)", 'histogram_quantile(0.95,sum by(le)(rate(inventory_flow_duration_seconds_bucket{round="ROUND"}[30s])))',"s"),
        ("Flujos fallidos por segundo", 'sum(rate(inventory_flow_requests_total{round="ROUND",outcome="error"}[30s])) or vector(0)',"reqps"),
    ]
    panels = []
    for row,(title,query,unit) in enumerate(queries):
        for column,round_name in enumerate(("R0","R1")):
            defaults = {"unit":unit,"min":0,"color":{"mode":"fixed","fixedColor":"blue" if column==0 else "orange"}}
            if unit=="percentunit":
                defaults["max"] = 1
            panels.append({"id":len(panels)+1,"type":"timeseries","title":round_name+" | "+title,
                           "gridPos":{"x":column*12,"y":row*7,"w":12,"h":7},
                           "datasource":{"type":"prometheus","uid":"prometheus"},
                           "targets":[{"refId":"A","expr":query.replace("ROUND",round_name),"legendFormat":round_name}],
                           "fieldConfig":{"defaults":defaults,"overrides":[]}})
    return {"uid":"inventory-chaos","title":"Inventario U - Caos R0 y R1","schemaVersion":41,
            "version":1,"refresh":"5s","timezone":"utc","tags":["chaos","R0","R1"],
            "time":{"from":"now-30m","to":"now"},"panels":panels,
            "annotations":{"list":[{"name":"Ventanas de caos","datasource":{"type":"grafana","uid":"-- Grafana --"},
                                     "enable":True,"hide":False,"iconColor":"red","type":"tags","tags":["inventario-chaos"]}]}}


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1]/"deploy/canary/grafana/dashboards/chaos.json"
    destination.write_text(json.dumps(build(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
