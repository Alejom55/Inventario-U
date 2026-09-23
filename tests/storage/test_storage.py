import json
from dataclasses import replace
from unittest.mock import Mock

import oci
import pytest

from app.storage.service import (
    StorageConfig, StorageError, crear_cliente, get_storage_service, nombre_objeto,
)


def test_guardar_utf8(storage, sdk):
    data = {"ciudad": "Bogotá", "emoji": "⚽", "inventario": {"stock": 2}}
    result = storage.guardar_json("abc-123", data)
    assert result.model_dump() == {
        "trace_id": "abc-123", "object_name": "flujos/abc-123.json",
        "bucket": "bucket-test", "status": "stored",
    }
    sdk.put_object.assert_called_once_with(
        namespace_name="namespace-test", bucket_name="bucket-test",
        object_name="flujos/abc-123.json", content_type="application/json",
        put_object_body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        opc_client_request_id="abc-123",
    )


def test_recuperar_utf8(storage, sdk):
    sdk.get_object.return_value.data.content = '{"ciudad":"Bogotá"}'.encode()
    assert storage.obtener_json("abc-123") == {"ciudad": "Bogotá"}
    sdk.get_object.assert_called_once_with(
        namespace_name="namespace-test", bucket_name="bucket-test",
        object_name="flujos/abc-123.json", opc_client_request_id="abc-123",
    )
    sdk.get_object.return_value.data.close.assert_called_once()


@pytest.mark.parametrize("trace", ["", "../x", "a/b", "a\\b", "a.json", "a\n", "á", "a" * 129, 123])
def test_trace_invalido(storage, sdk, trace):
    with pytest.raises(StorageError) as caught:
        storage.guardar_json(trace, {})
    assert caught.value.status_code == 422
    sdk.put_object.assert_not_called()


def test_limite_trace():
    assert nombre_objeto("a" * 128) == f"flujos/{'a' * 128}.json"


@pytest.mark.parametrize("data", [{"bad": object()}, {"bad": float("nan")}, {"bad": float("inf")}, [], {"bad": "\ud800"}])
def test_serializacion_invalida(storage, sdk, data):
    with pytest.raises(StorageError) as caught:
        storage.guardar_json("abc", data)
    assert caught.value.status_code == 422
    sdk.put_object.assert_not_called()


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'{"n":NaN}', b"\xff"])
def test_json_remoto_invalido(storage, sdk, payload):
    sdk.get_object.return_value.data.content = payload
    with pytest.raises(StorageError) as caught:
        storage.obtener_json("abc")
    assert caught.value.status_code == 502
    sdk.get_object.return_value.data.close.assert_called_once()


@pytest.mark.parametrize("status,code,expected", [
    (404, "ObjectNotFound", 404), (404, "BucketNotFound", 503),
    (404, "NotAuthorizedOrNotFound", 503), (401, "NotAuthenticated", 503),
    (403, "NotAuthorized", 503), (429, "TooManyRequests", 503),
    (500, "InternalServerError", 502), (408, "Timeout", 504), (504, "Timeout", 504),
])
def test_errores_oci(client, sdk, caplog, status, code, expected):
    sdk.get_object.side_effect = oci.exceptions.ServiceError(status, code, {}, "secret-private-key")
    response = client.get("/api/v2/storage/abc", headers={"X-Trace-Id": "request-123"})
    assert response.status_code == expected
    assert response.headers["X-Trace-Id"] == "request-123"
    assert "secret-private-key" not in response.text + caplog.text
    assert any(record.trace_id == "request-123" for record in caplog.records)
    assert any(record.trace_id == "abc" for record in caplog.records)


@pytest.mark.parametrize("error,expected", [
    (TimeoutError("secret"), 504),
    (oci._vendor.requests.exceptions.ReadTimeout("secret"), 504),
    (oci._vendor.requests.exceptions.ConnectionError("secret"), 502),
    (oci.exceptions.ClientError("secret"), 503),
    (oci.exceptions.RequestException(oci._vendor.requests.exceptions.ReadTimeout("secret")), 504),
    (oci.exceptions.RequestException(oci._vendor.requests.exceptions.ConnectionError("secret")), 502),
])
def test_timeout_red_sdk(client, sdk, error, expected):
    sdk.put_object.side_effect = error
    response = client.post("/api/v2/storage", json={"data": {}}, headers={"X-Trace-Id": "abc"})
    assert response.status_code == expected
    assert "secret" not in response.text


@pytest.mark.parametrize("body_trace,header_trace", [(None, None), ("body-123", None), (None, "header-123"), ("same", "same")])
def test_post_trace(client, sdk, body_trace, header_trace):
    body = {"data": {"inventario": {}, "deportista": {}, "articulo": {}}}
    if body_trace:
        body["trace_id"] = body_trace
    headers = {"X-Trace-Id": header_trace} if header_trace else {}
    response = client.post("/api/v2/storage", json=body, headers=headers)
    assert response.status_code == 201
    trace = header_trace or body_trace or response.headers["X-Trace-Id"]
    assert response.json()["trace_id"] == response.headers["X-Trace-Id"] == trace
    assert sdk.put_object.call_args.kwargs["object_name"] == f"flujos/{trace}.json"


@pytest.mark.parametrize("body,headers", [
    ({"trace_id": "other", "data": {}}, {"X-Trace-Id": "abc"}),
    ({"data": {}}, {"X-Trace-Id": "../bad"}),
    ({"trace_id": "../bad", "data": {}}, {}),
    ({"data": []}, {}), ({}, {}),
])
def test_post_rechaza_datos_invalidos(client, sdk, body, headers):
    assert client.post("/api/v2/storage", json=body, headers=headers).status_code == 422
    sdk.put_object.assert_not_called()


def test_get_endpoint(client, sdk):
    sdk.get_object.return_value.data.content = b'{"inventario":{}}'
    assert client.get("/api/v2/storage/abc").json() == {"inventario": {}}
    assert client.get("/api/v2/storage/bad.json").status_code == 422


@pytest.mark.parametrize("api_key", [None, "wrong", "correct"])
def test_api_key_y_health(client, sdk, monkeypatch, api_key):
    monkeypatch.setenv("TEAM_API_KEY", "correct")
    sdk.get_object.return_value.data.content = b"{}"
    headers = {"X-Api-Key": api_key} if api_key else {}
    post = client.post("/api/v2/storage", json={"data": {}}, headers=headers)
    get = client.get("/api/v2/storage/abc", headers=headers)
    assert post.status_code == (201 if api_key == "correct" else 401)
    assert get.status_code == (200 if api_key == "correct" else 401)
    if api_key != "correct":
        sdk.put_object.assert_not_called()
        sdk.get_object.assert_not_called()
    assert client.get("/health").json() == {"estado": "ok"}
    assert client.get("/api/v2/health").status_code == 200


def test_sin_configuracion(client, monkeypatch):
    monkeypatch.setattr("app.storage.router.get_storage_service", get_storage_service)
    assert client.post("/api/v2/storage", json={"data": {}}).status_code == 503
    assert client.get("/api/v2/health").status_code == 200


def test_fallo_inicializacion(client, monkeypatch):
    monkeypatch.setattr("app.storage.router.get_storage_service", Mock(side_effect=OSError("private-key")))
    response = client.get("/api/v2/storage/abc")
    assert response.status_code == 502
    assert "private-key" not in response.text


@pytest.mark.parametrize("mode,signer_name", [
    ("instance_principals", "InstancePrincipalsSecurityTokenSigner"),
    ("resource_principals", "get_resource_principals_signer"),
])
def test_signers(storage, monkeypatch, mode, signer_name):
    signer = Mock()
    signer_factory = Mock(return_value=signer)
    factory = Mock()
    monkeypatch.setattr(f"oci.auth.signers.{signer_name}", signer_factory)
    monkeypatch.setattr("oci.object_storage.ObjectStorageClient", factory)
    crear_cliente(replace(storage.config, auth_mode=mode))
    signer_factory.assert_called_once_with()
    assert factory.call_args.args == ({"region": "region-test"},)
    assert factory.call_args.kwargs["signer"] is signer
    assert factory.call_args.kwargs["timeout"] == (5, 30)


def test_config_local(storage, monkeypatch):
    reader = Mock(return_value={"region": "old", "user": "fake"})
    factory = Mock()
    monkeypatch.setattr("oci.config.from_file", reader)
    monkeypatch.setattr("oci.object_storage.ObjectStorageClient", factory)
    crear_cliente(replace(storage.config, auth_mode="config_file"))
    reader.assert_called_once_with("unused", "DEFAULT")
    assert factory.call_args.args[0] == {"region": "region-test", "user": "fake"}


def test_modo_invalido(storage):
    with pytest.raises(StorageError) as caught:
        crear_cliente(replace(storage.config, auth_mode="invalid"))
    assert caught.value.status_code == 503


def test_entorno_y_cache(monkeypatch):
    for name, value in {"OCI_NAMESPACE": "ns", "OCI_BUCKET_NAME": "bucket", "OCI_REGION": "region"}.items():
        monkeypatch.setenv(name, value)
    factory = Mock()
    monkeypatch.setattr("app.storage.service.crear_cliente", factory)
    assert StorageConfig.from_env().auth_mode == "instance_principals"
    assert get_storage_service() is get_storage_service()
    factory.assert_called_once()
