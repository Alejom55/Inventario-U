"""Archive sanitized cloud evidence in the existing private OCI bucket."""

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

import oci

from .gate import snapshot
from .rollout import FOLDER, load_env
from .smoke import request


def collect(values, action):
    def grafana(path):
        credentials = base64.b64encode(("admin:" + values["GRAFANA_PASSWORD"]).encode()).decode()
        req = Request("http://127.0.0.1:8000/grafana/api/" + path,
                      headers={"Authorization": "Basic " + credentials})
        with urlopen(req, timeout=10) as response:
            return json.load(response)

    dashboard = grafana("dashboards/uid/inventory-canary")
    datasource = grafana("datasources/uid/prometheus/health")
    status, _, inventory = request("http://127.0.0.1:8000", values["TEAM_API_KEY"],
                                   "/api/v2/inventario/query", "QUERY", {})
    if status != 200:
        raise RuntimeError("Cannot verify baseline inventory")
    events = [json.loads(line) for line in (FOLDER / "evidence/rollout.jsonl").read_text().splitlines()]
    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "environment": "OCI Compute",
        "action": action, "revision": values["APP_REVISION"], "image": values["CANARY_IMAGE"],
        "dashboard": {"title": dashboard["dashboard"]["title"],
                      "panels": len(dashboard["dashboard"]["panels"]),
                      "datasource_status": datasource["status"]},
        "inventory_rows": len(inventory["resultados"]),
        "inventory_sha256": hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
        "metrics": {track: snapshot("http://127.0.0.1:9090", track) for track in ("stable", "canary")},
        "events": events,
    }


def main(action):
    if action not in {"install", "promote", "regression", "rollback"}:
        raise ValueError("Invalid evidence action")
    values = load_env("/opt/inventario/canary.env")
    report = collect(values, action)
    body = json.dumps(report, ensure_ascii=False, allow_nan=False).encode()
    for name in ("TEAM_API_KEY", "GRAFANA_PASSWORD", "POSTGRES_PASSWORD"):
        if values[name].encode() in body:
            raise RuntimeError("Refusing to archive credentials")
    client = oci.object_storage.ObjectStorageClient(
        {"region": values["OCI_REGION"]},
        signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner(),
    )
    if action == "install":
        # Deliver operator access through private Object Storage, never command logs.
        access = json.dumps({"user": "admin", "password": values["GRAFANA_PASSWORD"]}).encode()
        client.put_object(values["OCI_NAMESPACE"], values["OCI_BUCKET_NAME"],
                          "canary-operator-access/" + values["APP_REVISION"] + ".json", access,
                          content_type="application/json")
    key = "canary-evidence/" + values["APP_REVISION"] + "/" + action + ".json"
    client.put_object(values["OCI_NAMESPACE"], values["OCI_BUCKET_NAME"], key, body,
                      content_type="application/json")
    print("Sanitized OCI evidence archived:", key, flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
