import os

from psycopg import connect
from psycopg.rows import dict_row


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://inventario:inventario@localhost:5432/inventario",
)

def get_db():
    """Abre una conexión a PostgreSQL y la cierra al terminar la solicitud."""
    db = connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield db
    finally:
        db.close()
