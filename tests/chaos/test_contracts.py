import pytest

from app.integrations.contracts import configuration_fingerprint, entity_path, path_template
from chaos_lab import contracts


@pytest.fixture
def group():
    return {"CHAOS_TARGET_URL": "https://inventory.example", "DEPORTBACK_API_URL": "https://person.example", "FASTIFY_API_URL": "https://article.example", "TEAM_API_KEY": "synthetic-secret", "SKU_ID": "1", "ALMACEN_ID": "2", "DEPORTISTA_ID": "person-1", "ARTICULO_ID": "7", "EXPECTED_APP_REVISION": "a"*40, "CHAOS_RUN_ID": "b"*32, "CHAOS_ROUND": "R0"}


def responses(group, mutate=None):
    def get(url, key, trace):
        assert key == group["TEAM_API_KEY"]
        headers = {"X-Trace-Id": trace}
        if url.startswith(group["DEPORTBACK_API_URL"]):
            body = {"id": "person-1"}
        elif url.startswith(group["FASTIFY_API_URL"]):
            body = {"id": 7}
        else:
            headers.update({"X-App-Revision": "a"*40, "X-Chaos-Round": "R0", "X-Resilience-Mode": "baseline", "X-Integration-Contract": configuration_fingerprint(group)})
            body = {"trace_id": trace, "inventario": {"sku_id": 1, "almacen_id": 2}, "deportista": {"id": "person-1"}, "articulo": {"id": 7}}
        if mutate:
            mutate(url, body, headers)
        return body, headers
    return get


def test_verifies_both_entities_and_full_coordinator(group, monkeypatch):
    monkeypatch.setattr(contracts, "get_json", responses(group))
    result = contracts.check_group(group)
    assert result["status"] == "verified" and len(result["dependencies"]) == 2
    assert group["TEAM_API_KEY"] not in str(result)


@pytest.mark.parametrize("header", ["X-Trace-Id", "X-App-Revision", "X-Chaos-Round", "X-Resilience-Mode", "X-Integration-Contract"])
def test_inconsistent_deployment_prevents_experiment(group, monkeypatch, header):
    def mutate(url, body, headers):
        if url.startswith(group["CHAOS_TARGET_URL"]):
            headers[header] = "wrong"
    monkeypatch.setattr(contracts, "get_json", responses(group, mutate))
    with pytest.raises(contracts.ContractError):
        contracts.check_group(group)


def test_wrong_companion_id_rejected(group, monkeypatch):
    def mutate(url, body, headers):
        if url.startswith(group["DEPORTBACK_API_URL"]):
            body["id"] = "another-person"
    monkeypatch.setattr(contracts, "get_json", responses(group, mutate))
    with pytest.raises(contracts.ContractError, match="another synthetic ID"):
        contracts.check_group(group)


def test_missing_configuration_never_sends_requests(monkeypatch):
    monkeypatch.setattr(contracts, "get_json", lambda *args: pytest.fail("No configured target"))
    with pytest.raises(contracts.ContractError, match="Missing configuration"):
        contracts.check_group({})


@pytest.mark.parametrize("url", ["https://user:password@example.com", "https://example.com?key=secret", "file:///etc/passwd", "//example.com"])
def test_credentials_and_unsupported_urls_rejected(url):
    with pytest.raises(contracts.ContractError):
        contracts._base(url)


def test_contract_path_and_nested_entity_identifier(monkeypatch):
    monkeypatch.setenv("DEPORTBACK_ENTITY_PATH", "/api/v1/deportistas/{id}")
    assert entity_path("deportBack", "id?extra") == "/api/v1/deportistas/id%3Fextra"
    assert contracts.identity_at({"data": {"id": 7}}, "data.id") == "7"
    with pytest.raises(ValueError):
        path_template("deportBack", {"DEPORTBACK_ENTITY_PATH": "//other-host/{id}"})
