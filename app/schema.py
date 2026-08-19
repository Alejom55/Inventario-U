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


def crear_tabla_movimientos():
    """Crea la tabla de movimientos si todavía no existe."""
    with connect(DATABASE_URL) as db:
        with db.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS movimientos (
                    id SERIAL PRIMARY KEY,
                    sku_id INTEGER NOT NULL REFERENCES skus(id) ON DELETE RESTRICT,
                    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
                    tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('entrada', 'salida', 'ajuste')),
                    cantidad INTEGER NOT NULL CHECK (cantidad <> 0),
                    motivo VARCHAR(255),
                    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'movimientos'
                          AND column_name = 'tipo'
                          AND udt_name = 'tipomovimiento'
                    ) THEN
                        ALTER TABLE movimientos
                        ALTER COLUMN tipo TYPE VARCHAR(10)
                        USING LOWER(tipo::text);
                    END IF;
                END $$;
                """
            )
            cursor.execute(
                "ALTER TABLE movimientos DROP CONSTRAINT IF EXISTS movimientos_tipo_check;"
            )
            cursor.execute(
                """
                ALTER TABLE movimientos
                ADD CONSTRAINT movimientos_tipo_check
                CHECK (tipo IN ('entrada', 'salida', 'ajuste'));
                """
            )
