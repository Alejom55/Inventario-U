import logging
import os

import httpx


logger = logging.getLogger(__name__)
TIMEOUT_SECONDS = 5.0


class ExternalApiError(Exception):
    """Error controlado al consultar una API externa."""

    def __init__(self, service: str, detail: str):
        self.service = service
        self.detail = detail
        super().__init__(detail)


def get_json(base_url: str | None, path: str, service: str, trace_id: str):
    if not base_url:
        raise ExternalApiError(service, f"{service} no está configurada")

    url = f"{base_url.rstrip('/')}{path}"
    headers = {"X-Trace-Id": trace_id}
    team_api_key = os.getenv("TEAM_API_KEY")
    if team_api_key:
        headers["X-Api-Key"] = team_api_key

    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        detail = f"{service} agotó el tiempo de espera"
    except httpx.HTTPStatusError as error:
        detail = f"{service} respondió HTTP {error.response.status_code}"
    except httpx.RequestError:
        detail = f"No fue posible conectar con {service}"
    except ValueError:
        detail = f"{service} devolvió una respuesta JSON inválida"

    logger.warning("Fallo al consultar %s: %s", service, detail, extra={"trace_id": trace_id})
    raise ExternalApiError(service, detail)
