from fastapi import Depends, FastAPI, HTTPException, status
from psycopg import errors

from .database import get_db
from .schema import crear_tabla_skus


app = FastAPI(
    title="Gestor de inventario",
    version="0.1.0",
    description="API para la gestión de SKU, almacenes y movimientos de inventario.",
)


@app.on_event("startup")
def iniciar_api():
    crear_tabla_skus()


@app.post("/skus", status_code=status.HTTP_201_CREATED)
def crear_sku(datos: dict, db=Depends(get_db)):
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
