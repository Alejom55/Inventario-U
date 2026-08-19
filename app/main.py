from fastapi import Depends, FastAPI, HTTPException, Response, status
from psycopg import errors

from .database import get_db
from .schema import crear_tabla_almacenes, crear_tabla_skus


app = FastAPI(
    title="Gestor de inventario",
    version="0.1.0",
    description="API para la gestión de SKU, almacenes y movimientos de inventario.",
)


@app.on_event("startup")
def iniciar_api():
    crear_tabla_skus()
    crear_tabla_almacenes()


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
