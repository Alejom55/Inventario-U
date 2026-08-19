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


def crear_tabla_almacenes():
    """Crea la tabla de almacenes si todavía no existe."""
    with connect(DATABASE_URL) as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS almacenes (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(120) UNIQUE NOT NULL,
                    ubicacion VARCHAR(255) NOT NULL
                );
                """
            )
