from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Response, status
from psycopg import errors

from .database import get_db
from .schema import crear_tabla_almacenes, crear_tabla_movimientos, crear_tabla_skus


app = FastAPI(
    title="Gestor de inventario",
    version="0.1.0",
    description="API para la gestión de SKU, almacenes y movimientos de inventario.",
)


@app.on_event("startup")
def iniciar_api():
    crear_tabla_skus()
    crear_tabla_almacenes()
    crear_tabla_movimientos()


@app.get("/health")
def estado_api():
    return {"estado": "ok"}


def validar_datos_sku(datos: dict):
    codigo = datos.get("codigo")
    nombre = datos.get("nombre")
    descripcion = datos.get("descripcion")
    stock_minimo = datos.get("stock_minimo", 0)

    if not isinstance(codigo, str) or not codigo.strip():
        raise HTTPException(status_code=400, detail="El código es obligatorio")
    if not isinstance(nombre, str) or not nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if descripcion is not None and not isinstance(descripcion, str):
        raise HTTPException(status_code=400, detail="La descripción debe ser texto")
    if isinstance(stock_minimo, bool) or not isinstance(stock_minimo, int) or stock_minimo < 0:
        raise HTTPException(status_code=400, detail="El stock mínimo debe ser un entero mayor o igual a cero")

    return codigo.strip(), nombre.strip(), descripcion, stock_minimo


@app.post("/skus", status_code=status.HTTP_201_CREATED)
def crear_sku(datos: dict, db=Depends(get_db)):
    codigo, nombre, descripcion, stock_minimo = validar_datos_sku(datos)

    try:
        resultado = db.execute(
            """
            INSERT INTO skus (codigo, nombre, descripcion, stock_minimo)
            VALUES (%s, %s, %s, %s)
            RETURNING id, codigo, nombre, descripcion, stock_minimo;
            """,
            (codigo.strip(), nombre.strip(), descripcion, stock_minimo),
        )
        sku = resultado.fetchone()
        db.commit()
        return sku
    except errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un SKU con ese código")


@app.get("/skus")
def listar_skus(db=Depends(get_db)):
    resultado = db.execute(
        """
        SELECT id, codigo, nombre, descripcion, stock_minimo
        FROM skus
        ORDER BY id;
        """
    )
    return resultado.fetchall()


@app.get("/skus/{sku_id}")
def consultar_sku(sku_id: int, db=Depends(get_db)):
    resultado = db.execute(
        """
        SELECT id, codigo, nombre, descripcion, stock_minimo
        FROM skus
        WHERE id = %s;
        """,
        (sku_id,),
    )
    sku = resultado.fetchone()

    if sku is None:
        raise HTTPException(status_code=404, detail="SKU no encontrado")

    return sku


@app.put("/skus/{sku_id}")
def actualizar_sku(sku_id: int, datos: dict, db=Depends(get_db)):
    codigo, nombre, descripcion, stock_minimo = validar_datos_sku(datos)

    try:
        resultado = db.execute(
            """
            UPDATE skus
            SET codigo = %s, nombre = %s, descripcion = %s, stock_minimo = %s
            WHERE id = %s
            RETURNING id, codigo, nombre, descripcion, stock_minimo;
            """,
            (codigo, nombre, descripcion, stock_minimo, sku_id),
        )
        sku = resultado.fetchone()
        if sku is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="SKU no encontrado")
        db.commit()
        return sku
    except errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un SKU con ese código")


@app.delete("/skus/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_sku(sku_id: int, db=Depends(get_db)):
    resultado = db.execute(
        "DELETE FROM skus WHERE id = %s RETURNING id;",
        (sku_id,),
    )
    sku = resultado.fetchone()

    if sku is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="SKU no encontrado")

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def validar_datos_almacen(datos: dict):
    nombre = datos.get("nombre")
    ubicacion = datos.get("ubicacion")

    if not isinstance(nombre, str) or not nombre.strip():
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    if not isinstance(ubicacion, str) or not ubicacion.strip():
        raise HTTPException(status_code=400, detail="La ubicación es obligatoria")

    return nombre.strip(), ubicacion.strip()


@app.post("/almacenes", status_code=status.HTTP_201_CREATED)
def crear_almacen(datos: dict, db=Depends(get_db)):
    nombre, ubicacion = validar_datos_almacen(datos)

    try:
        resultado = db.execute(
            """
            INSERT INTO almacenes (nombre, ubicacion)
            VALUES (%s, %s)
            RETURNING id, nombre, ubicacion;
            """,
            (nombre, ubicacion),
        )
        almacen = resultado.fetchone()
        db.commit()
        return almacen
    except errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un almacén con ese nombre")


@app.get("/almacenes")
def listar_almacenes(db=Depends(get_db)):
    resultado = db.execute(
        "SELECT id, nombre, ubicacion FROM almacenes ORDER BY id;"
    )
    return resultado.fetchall()


@app.get("/almacenes/{almacen_id}")
def consultar_almacen(almacen_id: int, db=Depends(get_db)):
    resultado = db.execute(
        "SELECT id, nombre, ubicacion FROM almacenes WHERE id = %s;",
        (almacen_id,),
    )
    almacen = resultado.fetchone()

    if almacen is None:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    return almacen


@app.put("/almacenes/{almacen_id}")
def actualizar_almacen(almacen_id: int, datos: dict, db=Depends(get_db)):
    nombre, ubicacion = validar_datos_almacen(datos)

    try:
        resultado = db.execute(
            """
            UPDATE almacenes
            SET nombre = %s, ubicacion = %s
            WHERE id = %s
            RETURNING id, nombre, ubicacion;
            """,
            (nombre, ubicacion, almacen_id),
        )
        almacen = resultado.fetchone()
        if almacen is None:
            db.rollback()
            raise HTTPException(status_code=404, detail="Almacén no encontrado")
        db.commit()
        return almacen
    except errors.UniqueViolation:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un almacén con ese nombre")


@app.delete("/almacenes/{almacen_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_almacen(almacen_id: int, db=Depends(get_db)):
    resultado = db.execute(
        "DELETE FROM almacenes WHERE id = %s RETURNING id;",
        (almacen_id,),
    )
    almacen = resultado.fetchone()

    if almacen is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Almacén no encontrado")

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


TIPOS_MOVIMIENTO = {"entrada", "salida", "ajuste"}


def validar_datos_movimiento(datos: dict):
    sku_id = datos.get("sku_id")
    almacen_id = datos.get("almacen_id")
    tipo = datos.get("tipo")
    cantidad = datos.get("cantidad")
    motivo = datos.get("motivo")

    if isinstance(sku_id, bool) or not isinstance(sku_id, int) or sku_id <= 0:
        raise HTTPException(status_code=400, detail="El SKU debe ser un número válido")
    if isinstance(almacen_id, bool) or not isinstance(almacen_id, int) or almacen_id <= 0:
        raise HTTPException(status_code=400, detail="El almacén debe ser un número válido")
    if tipo not in TIPOS_MOVIMIENTO:
        raise HTTPException(status_code=400, detail="El tipo debe ser entrada, salida o ajuste")
    if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad == 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser un entero diferente de cero")
    if tipo in {"entrada", "salida"} and cantidad < 0:
        raise HTTPException(status_code=400, detail="Las entradas y salidas deben tener cantidad positiva")
    if motivo is not None and not isinstance(motivo, str):
        raise HTTPException(status_code=400, detail="El motivo debe ser texto")

    return sku_id, almacen_id, tipo, cantidad, motivo


def verificar_sku_y_almacen(db, sku_id: int, almacen_id: int):
    sku = db.execute("SELECT id FROM skus WHERE id = %s;", (sku_id,)).fetchone()
    if sku is None:
        raise HTTPException(status_code=404, detail="SKU no encontrado")

    almacen = db.execute(
        "SELECT id FROM almacenes WHERE id = %s;", (almacen_id,)
    ).fetchone()
    if almacen is None:
        raise HTTPException(status_code=404, detail="Almacén no encontrado")


def cambio_en_stock(tipo: str, cantidad: int):
    if tipo == "salida":
        return -cantidad
    return cantidad


def calcular_stock(db, sku_id: int, almacen_id: int, excluir_movimiento_id: int | None = None):
    consulta = """
        SELECT COALESCE(SUM(
            CASE
                WHEN tipo = 'salida' THEN -cantidad
                ELSE cantidad
            END
        ), 0) AS stock
        FROM movimientos
        WHERE sku_id = %s AND almacen_id = %s
    """
    valores = [sku_id, almacen_id]

    if excluir_movimiento_id is not None:
        consulta += " AND id <> %s"
        valores.append(excluir_movimiento_id)

    return db.execute(consulta, valores).fetchone()["stock"]


def validar_stock_resultante(stock_actual: int, tipo: str, cantidad: int):
    if stock_actual + cambio_en_stock(tipo, cantidad) < 0:
        raise HTTPException(status_code=400, detail="El movimiento dejaría el inventario en negativo")


@app.post("/movimientos", status_code=status.HTTP_201_CREATED)
def crear_movimiento(datos: dict, db=Depends(get_db)):
    sku_id, almacen_id, tipo, cantidad, motivo = validar_datos_movimiento(datos)
    verificar_sku_y_almacen(db, sku_id, almacen_id)

    stock_actual = calcular_stock(db, sku_id, almacen_id)
    validar_stock_resultante(stock_actual, tipo, cantidad)

    resultado = db.execute(
        """
        INSERT INTO movimientos (sku_id, almacen_id, tipo, cantidad, motivo)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, sku_id, almacen_id, tipo, cantidad, motivo, fecha;
        """,
        (sku_id, almacen_id, tipo, cantidad, motivo),
    )
    movimiento = resultado.fetchone()
    db.commit()
    return movimiento


@app.get("/movimientos")
def listar_movimientos(
    sku_id: int | None = None,
    almacen_id: int | None = None,
    tipo: str | None = None,
    db=Depends(get_db),
):
    if tipo is not None and tipo not in TIPOS_MOVIMIENTO:
        raise HTTPException(status_code=400, detail="El tipo debe ser entrada, salida o ajuste")

    condiciones = []
    valores = []
    if sku_id is not None:
        condiciones.append("m.sku_id = %s")
        valores.append(sku_id)
    if almacen_id is not None:
        condiciones.append("m.almacen_id = %s")
        valores.append(almacen_id)
    if tipo is not None:
        condiciones.append("m.tipo = %s")
        valores.append(tipo)

    filtro_sql = ""
    if condiciones:
        filtro_sql = " WHERE " + " AND ".join(condiciones)

    resultado = db.execute(
        """
        SELECT m.id, m.sku_id, s.codigo AS sku_codigo, m.almacen_id,
               a.nombre AS almacen_nombre, m.tipo, m.cantidad, m.motivo, m.fecha
        FROM movimientos m
        JOIN skus s ON s.id = m.sku_id
        JOIN almacenes a ON a.id = m.almacen_id
        """ + filtro_sql + " ORDER BY m.fecha DESC, m.id DESC;",
        valores,
    )
    return resultado.fetchall()


@app.get("/movimientos/{movimiento_id}")
def consultar_movimiento(movimiento_id: int, db=Depends(get_db)):
    resultado = db.execute(
        """
        SELECT id, sku_id, almacen_id, tipo, cantidad, motivo, fecha
        FROM movimientos
        WHERE id = %s;
        """,
        (movimiento_id,),
    )
    movimiento = resultado.fetchone()

    if movimiento is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    return movimiento


@app.put("/movimientos/{movimiento_id}")
def actualizar_movimiento(movimiento_id: int, datos: dict, db=Depends(get_db)):
    sku_id, almacen_id, tipo, cantidad, motivo = validar_datos_movimiento(datos)
    movimiento_actual = db.execute(
        "SELECT id, sku_id, almacen_id FROM movimientos WHERE id = %s;", (movimiento_id,)
    ).fetchone()
    if movimiento_actual is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    verificar_sku_y_almacen(db, sku_id, almacen_id)

    stock_origen_sin_movimiento = calcular_stock(
        db,
        movimiento_actual["sku_id"],
        movimiento_actual["almacen_id"],
        movimiento_id,
    )
    if stock_origen_sin_movimiento < 0:
        raise HTTPException(
            status_code=400,
            detail="No se puede modificar porque el inventario de origen quedaría en negativo",
        )

    stock_sin_movimiento = calcular_stock(db, sku_id, almacen_id, movimiento_id)
    validar_stock_resultante(stock_sin_movimiento, tipo, cantidad)

    resultado = db.execute(
        """
        UPDATE movimientos
        SET sku_id = %s, almacen_id = %s, tipo = %s, cantidad = %s, motivo = %s
        WHERE id = %s
        RETURNING id, sku_id, almacen_id, tipo, cantidad, motivo, fecha;
        """,
        (sku_id, almacen_id, tipo, cantidad, motivo, movimiento_id),
    )
    db.commit()
    return resultado.fetchone()


@app.delete("/movimientos/{movimiento_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_movimiento(movimiento_id: int, db=Depends(get_db)):
    movimiento = db.execute(
        """
        SELECT id, sku_id, almacen_id
        FROM movimientos
        WHERE id = %s;
        """,
        (movimiento_id,),
    ).fetchone()
    if movimiento is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    stock_sin_movimiento = calcular_stock(
        db, movimiento["sku_id"], movimiento["almacen_id"], movimiento_id
    )
    if stock_sin_movimiento < 0:
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar porque el inventario quedaría en negativo",
        )

    db.execute("DELETE FROM movimientos WHERE id = %s;", (movimiento_id,))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def validar_fecha(fecha, campo: str):
    if fecha is None:
        return None
    if not isinstance(fecha, str):
        raise HTTPException(status_code=400, detail=f"{campo} debe ser una fecha ISO 8601")
    try:
        return datetime.fromisoformat(fecha.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{campo} debe ser una fecha ISO 8601")


def validar_filtros_inventario(filtros: dict):
    sku_id = filtros.get("sku_id")
    almacen_id = filtros.get("almacen_id")
    tipo = filtros.get("tipo")
    fecha_desde = validar_fecha(filtros.get("fecha_desde"), "fecha_desde")
    fecha_hasta = validar_fecha(filtros.get("fecha_hasta"), "fecha_hasta")
    solo_stock_bajo = filtros.get("solo_stock_bajo", False)

    if sku_id is not None and (isinstance(sku_id, bool) or not isinstance(sku_id, int) or sku_id <= 0):
        raise HTTPException(status_code=400, detail="El SKU debe ser un número válido")
    if almacen_id is not None and (
        isinstance(almacen_id, bool) or not isinstance(almacen_id, int) or almacen_id <= 0
    ):
        raise HTTPException(status_code=400, detail="El almacén debe ser un número válido")
    if tipo is not None and tipo not in TIPOS_MOVIMIENTO:
        raise HTTPException(status_code=400, detail="El tipo debe ser entrada, salida o ajuste")
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        raise HTTPException(status_code=400, detail="fecha_desde no puede ser posterior a fecha_hasta")
    if not isinstance(solo_stock_bajo, bool):
        raise HTTPException(status_code=400, detail="solo_stock_bajo debe ser verdadero o falso")

    return sku_id, almacen_id, tipo, fecha_desde, fecha_hasta, solo_stock_bajo


@app.options("/inventario/query")
def opciones_query():
    return Response(headers={"Accept-Query": "application/json"})


@app.api_route("/inventario/query", methods=["QUERY"])
def consultar_inventario(filtros: dict, db=Depends(get_db)):
    sku_id, almacen_id, tipo, fecha_desde, fecha_hasta, solo_stock_bajo = (
        validar_filtros_inventario(filtros)
    )

    condiciones = []
    valores = []
    if sku_id is not None:
        condiciones.append("i.sku_id = %s")
        valores.append(sku_id)
    if almacen_id is not None:
        condiciones.append("i.almacen_id = %s")
        valores.append(almacen_id)
    if solo_stock_bajo:
        condiciones.append("i.stock_disponible <= i.stock_minimo")

    filtro_movimiento = []
    valores_movimiento = []
    if tipo is not None:
        filtro_movimiento.append("mf.tipo = %s")
        valores_movimiento.append(tipo)
    if fecha_desde is not None:
        filtro_movimiento.append("mf.fecha >= %s")
        valores_movimiento.append(fecha_desde)
    if fecha_hasta is not None:
        filtro_movimiento.append("mf.fecha <= %s")
        valores_movimiento.append(fecha_hasta)
    if filtro_movimiento:
        condiciones.append(
            """EXISTS (
                SELECT 1
                FROM movimientos mf
                WHERE mf.sku_id = i.sku_id
                  AND mf.almacen_id = i.almacen_id
                  AND """ + " AND ".join(filtro_movimiento) + ")"
        )
        valores.extend(valores_movimiento)

    filtro_sql = ""
    if condiciones:
        filtro_sql = " WHERE " + " AND ".join(condiciones)

    resultado = db.execute(
        """
        WITH inventario AS (
            SELECT s.id AS sku_id, s.codigo AS sku_codigo, s.nombre AS sku_nombre,
                   s.stock_minimo, a.id AS almacen_id, a.nombre AS almacen_nombre,
                   COALESCE(SUM(
                       CASE WHEN m.tipo = 'salida' THEN -m.cantidad ELSE m.cantidad END
                   ), 0) AS stock_disponible
            FROM skus s
            CROSS JOIN almacenes a
            LEFT JOIN movimientos m ON m.sku_id = s.id AND m.almacen_id = a.id
            GROUP BY s.id, s.codigo, s.nombre, s.stock_minimo, a.id, a.nombre
        )
        SELECT sku_id, sku_codigo, sku_nombre, stock_minimo,
               almacen_id, almacen_nombre, stock_disponible
        FROM inventario i
        """ + filtro_sql + " ORDER BY i.sku_codigo, i.almacen_nombre;",
        valores,
    )

    return {"resultados": resultado.fetchall()}
