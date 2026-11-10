import logging
import os

import httpx

from .resilience import CircuitOpen, observe, protection


logger = logging.getLogger(__name__)


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
        timeout, breaker = protection(service, base_url)
    except ValueError:
        raise ExternalApiError(service, "Configuración de resiliencia inválida") from None
    ticket = None
    if breaker:
        try:
            ticket = breaker.acquire()
        except CircuitOpen:
            observe(service, breaker)
            logger.warning("Circuito abierto", extra={"trace_id": trace_id, "service": service})
            raise ExternalApiError(service, f"{service} tiene el circuito abierto") from None
    observe(service, breaker)

    counts_as_failure = True
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()
        if breaker:
            breaker.success(ticket)
        observe(service, breaker)
        return result
    except httpx.TimeoutException:
        detail = f"{service} agotó el tiempo de espera"
    except httpx.HTTPStatusError as error:
        detail = f"{service} respondió HTTP {error.response.status_code}"
        counts_as_failure = error.response.status_code >= 500
    except httpx.RequestError:
        detail = f"No fue posible conectar con {service}"
    except ValueError:
        detail = f"{service} devolvió una respuesta JSON inválida"

    if breaker:
        if counts_as_failure:
            breaker.failure(ticket)
        else:
            breaker.success(ticket)
    observe(service, breaker)

    logger.warning("Fallo al consultar %s: %s", service, detail, extra={"trace_id": trace_id})
    raise ExternalApiError(service, detail)
