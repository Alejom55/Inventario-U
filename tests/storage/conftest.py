from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage.service import ObjectStorageService, StorageConfig, get_storage_service


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Storage no usa PostgreSQL; sustituye el fixture global solo en esta carpeta."""


@pytest.fixture(autouse=True)
def aislar_oci(monkeypatch):
    get_storage_service.cache_clear()
    for name in ("OCI_NAMESPACE", "OCI_BUCKET_NAME", "OCI_REGION", "OCI_AUTH_MODE", "TEAM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    # Una llamada no simulada al SDK falla antes de acceder a credenciales o red.
    for name in (
        "InstancePrincipalsSecurityTokenSigner",
        "get_resource_principals_signer",
    ):
        monkeypatch.setattr(f"oci.auth.signers.{name}", Mock(side_effect=AssertionError("OCI real prohibido")))
    monkeypatch.setattr("oci.config.from_file", Mock(side_effect=AssertionError("Credenciales reales prohibidas")))
    monkeypatch.setattr("oci.object_storage.ObjectStorageClient", Mock(side_effect=AssertionError("OCI real prohibido")))
    yield
    get_storage_service.cache_clear()


@pytest.fixture
def sdk():
    return Mock()


@pytest.fixture
def storage(sdk):
    return ObjectStorageService(
        StorageConfig("namespace-test", "bucket-test", "region-test", "instance_principals", "unused", "DEFAULT"),
        sdk,
    )


@pytest.fixture
def client(monkeypatch, storage):
    monkeypatch.setattr("app.storage.router.get_storage_service", lambda: storage)
    # Evita únicamente startup PostgreSQL; conserva app, rutas y middleware reales.
    monkeypatch.setattr("app.main.crear_tabla_skus", lambda: None)
    monkeypatch.setattr("app.main.crear_tabla_almacenes", lambda: None)
    monkeypatch.setattr("app.main.crear_tabla_movimientos", lambda: None)
    with TestClient(app) as test_client:
        yield test_client
