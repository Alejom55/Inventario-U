import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from .schemas import GuardarJsonRequest, JsonGuardado, TraceId
from .service import ObjectStorageService, StorageError, get_storage_service, nombre_objeto, traducir_error


logger = logging.getLogger(__name__)
router = APIRouter(tags=["storage"])


def storage_dependency(request: Request) -> ObjectStorageService:
    try:
        return get_storage_service()
    except StorageError as error:
        raise error_http(error, request) from None
    except Exception as error:
        raise error_http(traducir_error(error, request.state.trace_id), request) from None


def error_http(error: StorageError, request: Request) -> HTTPException:
    logger.warning("Operación de storage rechazada", extra={"trace_id": request.state.trace_id})
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.post("/storage", response_model=JsonGuardado, status_code=201)
def guardar_json(
    datos: GuardarJsonRequest,
    request: Request,
    storage: ObjectStorageService = Depends(storage_dependency),
):
    header_trace = request.headers.get("X-Trace-Id")
    if header_trace and datos.trace_id and header_trace != datos.trace_id:
        raise HTTPException(422, "trace_id y X-Trace-Id deben coincidir")
    trace_id = header_trace or datos.trace_id or request.state.trace_id
    try:
        nombre_objeto(trace_id)
        request.state.trace_id = trace_id
        return storage.guardar_json(trace_id, datos.data)
    except StorageError as error:
        raise error_http(error, request) from None


@router.get("/storage/{trace_id}")
def obtener_json(
    trace_id: TraceId,
    request: Request,
    storage: ObjectStorageService = Depends(storage_dependency),
):
    try:
        return storage.obtener_json(trace_id)
    except StorageError as error:
        raise error_http(error, request) from None
