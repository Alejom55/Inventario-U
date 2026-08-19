import os

from psycopg import connect, sql


ADMIN_DATABASE_URL = os.getenv(
    "ADMIN_DATABASE_URL",
    "postgresql://inventario:inventario@localhost:5432/postgres",
)
TEST_DATABASE_NAME = os.getenv("TEST_DATABASE_NAME", "inventario_test")


with connect(ADMIN_DATABASE_URL, autocommit=True) as db:
    existe = db.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s;",
        (TEST_DATABASE_NAME,),
    ).fetchone()

    if not existe:
        db.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(TEST_DATABASE_NAME)))
        print(f"Base de pruebas creada: {TEST_DATABASE_NAME}")
    else:
        print(f"La base de pruebas ya existe: {TEST_DATABASE_NAME}")
