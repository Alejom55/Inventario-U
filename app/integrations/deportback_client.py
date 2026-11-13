import os

from .external_api import get_json
from .contracts import entity_path


def obtener_deportista(deportista_id: str, trace_id: str):
    """Consulta la entidad propietaria para evitar dependencias circulares."""
    return get_json(
        os.getenv("DEPORTBACK_API_URL"),
        entity_path("deportBack", deportista_id),
        "deportBack",
        trace_id,
    )
