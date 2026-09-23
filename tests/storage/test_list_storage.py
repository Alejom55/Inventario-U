from datetime import datetime, timezone

import oci
import pytest


def pagina(sdk, names, next_start=None):
    sdk.list_objects.return_value.data = oci.object_storage.models.ListObjects(
        objects=[oci.object_storage.models.ObjectSummary(
            name=name, size=42,
            time_created=datetime(2026, 9, 23, tzinfo=timezone.utc),
            time_modified=datetime(2026, 9, 23, tzinfo=timezone.utc),
        ) for name in names],
        next_start_with=next_start,
    )


def test_lista_bucket_completo_y_trace(client, sdk):
    pagina(sdk, ["flujos/abc.json", "otros/archivo.txt"])
    response = client.get("/api/v2/storage", headers={"X-Trace-Id": "lista-123"})
    assert response.status_code == 200
    assert response.headers["X-Trace-Id"] == "lista-123"
    data = response.json()
    assert data["bucket"] == "bucket-test"
    assert data["next_start"] is None
    assert [obj["object_name"] for obj in data["objects"]] == ["flujos/abc.json", "otros/archivo.txt"]
    assert data["objects"][0]["size"] == 42
    assert data["objects"][0]["time_created"] == "2026-09-23T00:00:00Z"
    sdk.list_objects.assert_called_once_with(
        namespace_name="namespace-test", bucket_name="bucket-test", limit=100,
        prefix="", start=None, fields="name,size,timeCreated,timeModified",
        opc_client_request_id="lista-123",
    )
    sdk.get_object.assert_not_called()


def test_paginacion_y_prefijo(client, sdk):
    pagina(sdk, ["flujos/a.json"], "flujos/b +ñ.json")
    first = client.get("/api/v2/storage", params={"limit": 1, "prefix": "flujos/"}).json()
    pagina(sdk, ["flujos/b +ñ.json"])
    second = client.get("/api/v2/storage", params={
        "limit": 1, "prefix": "flujos/", "start": first["next_start"],
    })
    assert second.status_code == 200
    assert second.json()["next_start"] is None
    assert sdk.list_objects.call_args.kwargs["start"] == "flujos/b +ñ.json"
    assert sdk.list_objects.call_args.kwargs["prefix"] == "flujos/"
    assert sdk.list_objects.call_args.kwargs["limit"] == 1


def test_bucket_vacio(client, sdk):
    pagina(sdk, [])
    assert client.get("/api/v2/storage").json() == {
        "bucket": "bucket-test", "objects": [], "next_start": None,
    }


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 1001}, {"limit": "abc"}, {"start": ""}])
def test_parametros_invalidos(client, sdk, params):
    assert client.get("/api/v2/storage", params=params).status_code == 422
    sdk.list_objects.assert_not_called()


@pytest.mark.parametrize("key", [None, "wrong", "correct"])
def test_listado_protegido(client, sdk, monkeypatch, key):
    monkeypatch.setenv("TEAM_API_KEY", "correct")
    pagina(sdk, [])
    response = client.get("/api/v2/storage", headers={"X-Api-Key": key} if key else {})
    assert response.status_code == (200 if key == "correct" else 401)
    if key != "correct":
        sdk.list_objects.assert_not_called()


@pytest.mark.parametrize("error,expected", [
    (oci.exceptions.ServiceError(403, "NotAuthorized", {}, "secret"), 503),
    (oci.exceptions.ServiceError(404, "BucketNotFound", {}, "secret"), 503),
    (TimeoutError("secret"), 504),
    (oci.exceptions.RequestException("secret"), 502),
])
def test_errores_listado(client, sdk, caplog, error, expected):
    sdk.list_objects.side_effect = error
    response = client.get("/api/v2/storage", headers={"X-Trace-Id": "lista-123"})
    assert response.status_code == expected
    assert "secret" not in response.text + caplog.text
    assert any(record.trace_id == "lista-123" for record in caplog.records)
