"""Read-only checks of real entity routes, identity and the deployed coordinator."""

import json
import hashlib
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.integrations.contracts import configuration_fingerprint, path_template


class ContractError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        raise ContractError("Redirect rejected: credentials must stay at the configured API")


def get_json(url, key, trace):
    request = Request(url, headers={"X-Api-Key": key, "X-Trace-Id": trace})
    try:
        with build_opener(NoRedirect).open(request, timeout=8) as response:
            payload = response.read(1_048_577)
            if len(payload) > 1_048_576:
                raise ContractError("Entity response exceeds 1 MiB")
            return json.loads(payload), response.headers
    except HTTPError as error:
        raise ContractError("Entity request returned HTTP " + str(error.code)) from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeError):
        raise ContractError("Entity request failed or returned invalid JSON") from None


def _base(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ContractError("API base URLs must not embed credentials, query strings or fragments")
    return value.rstrip("/")


def identity_at(entity, selector):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,5}", selector):
        raise ContractError("Invalid entity ID field selector")
    for field in selector.split("."):
        if not isinstance(entity, dict) or field not in entity:
            raise ContractError("Expected synthetic entity ID is missing")
        entity = entity[field]
    if isinstance(entity, bool) or not isinstance(entity, (str, int)):
        raise ContractError("Entity ID must be a string or integer")
    return str(entity)


def check_group(environment=None):
    env = os.environ if environment is None else environment
    required = ["CHAOS_TARGET_URL", "DEPORTBACK_API_URL", "FASTIFY_API_URL", "TEAM_API_KEY", "SKU_ID", "ALMACEN_ID", "DEPORTISTA_ID", "ARTICULO_ID", "EXPECTED_APP_REVISION", "CHAOS_RUN_ID", "CHAOS_ROUND"]
    missing = [name for name in required if not env.get(name)]
    if missing:
        raise ContractError("Missing configuration: " + ", ".join(missing))
    if env["CHAOS_ROUND"] not in {"R0", "R1"} or not re.fullmatch(r"[a-f0-9]{32}", env["CHAOS_RUN_ID"]) or not re.fullmatch(r"[a-f0-9]{40}", env["EXPECTED_APP_REVISION"]):
        raise ContractError("Invalid round, run ID or installed Git revision")
    for name in ("SKU_ID", "ALMACEN_ID", "ARTICULO_ID"):
        if not re.fullmatch(r"[1-9][0-9]*", str(env[name])):
            raise ContractError("Synthetic numeric IDs must be positive integers")
    base = _base(env["CHAOS_TARGET_URL"])
    key = env["TEAM_API_KEY"]
    run_id = env["CHAOS_RUN_ID"]
    verified = []
    for service, variable, id_variable, field_variable in [
        ("deportBack", "DEPORTBACK_API_URL", "DEPORTISTA_ID", "DEPORTBACK_ID_FIELD"),
        ("api-fastify", "FASTIFY_API_URL", "ARTICULO_ID", "FASTIFY_ID_FIELD"),
    ]:
        template = path_template(service, env)
        route = template.replace("{id}", quote(str(env[id_variable]), safe=""))
        trace = "contract-" + run_id + ("-deport" if service == "deportBack" else "-article")
        body, headers = get_json(_base(env[variable]) + route, key, trace)
        if headers.get("X-Trace-Id") != trace:
            raise ContractError(service + " does not echo X-Trace-Id")
        if identity_at(body, env.get(field_variable) or "id") != str(env[id_variable]):
            raise ContractError(service + " returned another synthetic ID")
        verified.append({"service": service, "route_template": template, "trace_id": trace})
    trace = "flow-" + run_id
    parameters = dict(sku_id=env["SKU_ID"], almacen_id=env["ALMACEN_ID"], deportista_id=env["DEPORTISTA_ID"], articulo_id=env["ARTICULO_ID"])
    body, headers = get_json(base + "/api/v2/integracion?" + urlencode(parameters), key, trace)
    expected = {
        "X-Trace-Id": trace, "X-App-Revision": env["EXPECTED_APP_REVISION"],
        "X-Chaos-Round": env["CHAOS_ROUND"],
        "X-Resilience-Mode": "baseline" if env["CHAOS_ROUND"] == "R0" else "protected",
        "X-Integration-Contract": configuration_fingerprint(env),
    }
    if any(headers.get(name) != value for name, value in expected.items()):
        raise ContractError("Coordinator revision, round, trace or dependency configuration does not match")
    if not isinstance(body, dict) or body.get("trace_id") != trace:
        raise ContractError("Coordinator returned an invalid flow envelope")
    inventory = body.get("inventario")
    for field in ("sku_id", "almacen_id"):
        if not isinstance(inventory, dict) or str(inventory.get(field)) != parameters[field]:
            raise ContractError("Coordinator returned another inventory identity")
    for entity, id_variable, field_variable in [("deportista", "DEPORTISTA_ID", "DEPORTBACK_ID_FIELD"), ("articulo", "ARTICULO_ID", "FASTIFY_ID_FIELD")]:
        if identity_at(body.get(entity), env.get(field_variable) or "id") != str(env[id_variable]):
            raise ContractError("Coordinator returned another companion entity")
    group_configuration = {name: env[name] for name in ("CHAOS_TARGET_URL","SKU_ID","ALMACEN_ID","DEPORTISTA_ID","ARTICULO_ID")}
    group_configuration["contracts"] = configuration_fingerprint(env)
    group_configuration["id_fields"] = [env.get(name) or "id" for name in ("DEPORTBACK_ID_FIELD","FASTIFY_ID_FIELD")]
    return {"status": "verified", "scope": "HTTP contracts and flow; cloud placement and Kubernetes are not inferred from URLs", "round": env["CHAOS_ROUND"], "revision": env["EXPECTED_APP_REVISION"], "group_fingerprint": hashlib.sha256(json.dumps(group_configuration,sort_keys=True).encode()).hexdigest(), "flow_trace_id": trace, "dependencies": verified}
