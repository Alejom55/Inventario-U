from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


TRACE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
TraceId = Annotated[str, Field(pattern=TRACE_ID_PATTERN, max_length=128)]


class GuardarJsonRequest(BaseModel):
    trace_id: TraceId | None = None
    data: dict[str, Any]


class JsonGuardado(BaseModel):
    trace_id: str
    object_name: str
    bucket: str
    status: Literal["stored"] = "stored"
