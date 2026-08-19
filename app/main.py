from fastapi import FastAPI

from .schema import crear_tabla_skus


app = FastAPI(
    title="Gestor de inventario",
    version="0.1.0",
    description="API para la gestión de SKU, almacenes y movimientos de inventario.",
)


@app.on_event("startup")
def iniciar_api():
    crear_tabla_skus()
