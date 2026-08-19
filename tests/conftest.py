import os

# Debe establecerse antes de importar la aplicación, porque la conexión se
# configura al cargar app.database.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://inventario:inventario@localhost:5432/inventario_test",
)

import pytest
from fastapi.testclient import TestClient
from psycopg import connect

from app.database import DATABASE_URL
from app.main import app
from app.schema import crear_tabla_almacenes, crear_tabla_movimientos, crear_tabla_skus


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    crear_tabla_skus()
    crear_tabla_almacenes()
    crear_tabla_movimientos()

    with connect(DATABASE_URL) as db:
        db.execute("TRUNCATE movimientos, almacenes, skus RESTART IDENTITY;")


@pytest.fixture
def client():
    with TestClient(app) as cliente:
        yield cliente
