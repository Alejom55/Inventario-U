import os

from .external_api import get_json


def obtener_deportista(deportista_id: str, trace_id: str):
    """Consulta la entidad propietaria para evitar dependencias circulares."""
    return get_json(
        os.getenv("DEPORTBACK_API_URL"),
        f"/deportistas/{deportista_id}",
        "deportBack",
        trace_id,
    )
