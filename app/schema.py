from psycopg import connect

from .database import DATABASE_URL


def crear_tabla_skus():
    with connect(DATABASE_URL) as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS skus (
                    id SERIAL PRIMARY KEY,
                    codigo VARCHAR(50) UNIQUE NOT NULL,
                    nombre VARCHAR(150) NOT NULL,
                    descripcion TEXT,
                    stock_minimo INTEGER NOT NULL DEFAULT 0,
                    CHECK (stock_minimo >= 0)
                );
                """
            )
