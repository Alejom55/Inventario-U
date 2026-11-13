import os

from .external_api import get_json
from .contracts import entity_path


def obtener_articulo(articulo_id: int, trace_id: str):
    """Consulta la entidad propietaria para evitar dependencias circulares."""
    return get_json(
        os.getenv("FASTIFY_API_URL"),
        entity_path("api-fastify", articulo_id),
        "api-fastify",
        trace_id,
    )
