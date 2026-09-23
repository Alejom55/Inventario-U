import json
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import oci

from .schemas import TRACE_ID_PATTERN, JsonGuardado, ListadoStorage, ObjetoStorage


logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Error público controlado; nunca contiene el mensaje original del SDK."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def nombre_objeto(trace_id: str) -> str:
    if not isinstance(trace_id, str) or not re.fullmatch(TRACE_ID_PATTERN, trace_id):
        raise StorageError(422, "trace_id debe tener entre 1 y 128 caracteres alfanuméricos, guiones o guiones bajos")
    return f"flujos/{trace_id}.json"


@dataclass(frozen=True)
class StorageConfig:
    namespace: str
    bucket: str
    region: str
    auth_mode: str
    config_file: str
    config_profile: str

    @classmethod
    def from_env(cls) -> "StorageConfig":
        config = cls(
            namespace=os.getenv("OCI_NAMESPACE", "").strip(),
            bucket=os.getenv("OCI_BUCKET_NAME", "").strip(),
            region=os.getenv("OCI_REGION", "").strip(),
            auth_mode=os.getenv("OCI_AUTH_MODE", "instance_principals").strip(),
            config_file=os.getenv("OCI_CONFIG_FILE", "~/.oci/config"),
            config_profile=os.getenv("OCI_CONFIG_PROFILE", "DEFAULT"),
        )
        if not all((config.namespace, config.bucket, config.region)):
            raise StorageError(503, "El almacenamiento no está configurado")
        return config


def crear_cliente(config: StorageConfig) -> oci.object_storage.ObjectStorageClient:
    """Construye el cliente al primer uso, sin consultar OCI al iniciar la API."""
    sdk_config = {"region": config.region}
    options: dict[str, Any] = {
        "timeout": (5, 30),
        "retry_strategy": oci.retry.NoneRetryStrategy(),
    }
    if config.auth_mode == "instance_principals":
        options["signer"] = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    elif config.auth_mode == "resource_principals":
        options["signer"] = oci.auth.signers.get_resource_principals_signer()
    elif config.auth_mode == "config_file":
        sdk_config = oci.config.from_file(
            os.path.expanduser(config.config_file), config.config_profile
        )
        sdk_config["region"] = config.region
    else:
        raise StorageError(503, "El modo de autenticación de almacenamiento no está configurado correctamente")
    return oci.object_storage.ObjectStorageClient(sdk_config, **options)


class ObjectStorageService:
    def __init__(self, config: StorageConfig, client: Any):
        self.config = config
        self.client = client

    def listar_objetos(
        self, trace_id: str, *, limit: int = 100, prefix: str = "", start: str | None = None,
    ) -> ListadoStorage:
        """Lista una página de objetos actuales del bucket sin descargar su contenido."""
        try:
            response = self.client.list_objects(
                namespace_name=self.config.namespace,
                bucket_name=self.config.bucket,
                limit=limit,
                prefix=prefix,
                start=start,
                fields="name,size,timeCreated,timeModified",
                opc_client_request_id=trace_id,
            )
            return ListadoStorage(
                bucket=self.config.bucket,
                objects=[
                    ObjetoStorage(
                        object_name=obj.name, size=obj.size,
                        time_created=obj.time_created, time_modified=obj.time_modified,
                    )
                    for obj in response.data.objects
                ],
                next_start=response.data.next_start_with,
            )
        except Exception as error:
            raise traducir_error(error, trace_id) from None

    def guardar_json(self, trace_id: str, contenido: dict[str, Any]) -> JsonGuardado:
        object_name = nombre_objeto(trace_id)
        try:
            if not isinstance(contenido, dict):
                raise TypeError("Se requiere un diccionario")
            payload = json.dumps(contenido, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise StorageError(422, "El contenido debe ser un objeto JSON válido") from None
        try:
            self.client.put_object(
                namespace_name=self.config.namespace,
                bucket_name=self.config.bucket,
                object_name=object_name,
                put_object_body=payload,
                content_type="application/json",
                opc_client_request_id=trace_id,
            )
        except Exception as error:
            raise traducir_error(error, trace_id) from None
        logger.info("JSON almacenado", extra={"trace_id": trace_id})
        return JsonGuardado(trace_id=trace_id, object_name=object_name, bucket=self.config.bucket)

    def obtener_json(self, trace_id: str) -> dict[str, Any]:
        object_name = nombre_objeto(trace_id)
        try:
            response = self.client.get_object(
                namespace_name=self.config.namespace,
                bucket_name=self.config.bucket,
                object_name=object_name,
                opc_client_request_id=trace_id,
            )
            try:
                contenido = json.loads(response.data.content.decode("utf-8"))
                if not isinstance(contenido, dict):
                    raise ValueError("Se requiere un objeto JSON")
                # Rechaza NaN/Infinity aceptados por defecto por json.loads.
                json.dumps(contenido, allow_nan=False)
            finally:
                response.data.close()
        except (ValueError, UnicodeError, RecursionError):
            logger.warning("JSON almacenado inválido", extra={"trace_id": trace_id})
            raise StorageError(502, "El archivo almacenado no contiene un objeto JSON válido") from None
        except Exception as error:
            raise traducir_error(error, trace_id, lectura=True) from None
        return contenido


def traducir_error(error: Exception, trace_id: str, *, lectura: bool = False) -> StorageError:
    # No registrar mensajes, cabeceras, URL ni cuerpos del SDK: pueden incluir secretos.
    logger.warning("Fallo de almacenamiento: %s", type(error).__name__, extra={"trace_id": trace_id})
    if isinstance(error, oci.exceptions.ServiceError):
        if lectura and error.status == 404 and error.code == "ObjectNotFound":
            return StorageError(404, "Archivo no encontrado")
        if error.status in (408, 504):
            return StorageError(504, "El almacenamiento agotó el tiempo de espera")
        if error.status in (401, 403, 404, 429, 503):
            return StorageError(503, "El almacenamiento no está disponible; revisa su configuración y permisos")
    if isinstance(error, (TimeoutError, oci._vendor.requests.exceptions.Timeout)):
        return StorageError(504, "El almacenamiento agotó el tiempo de espera")
    if isinstance(error, oci.exceptions.RequestException) and error.args:
        if isinstance(error.args[0], oci._vendor.requests.exceptions.Timeout):
            return StorageError(504, "El almacenamiento agotó el tiempo de espera")
    if isinstance(error, oci.exceptions.ClientError):
        return StorageError(503, "El almacenamiento no está disponible; revisa su configuración y permisos")
    return StorageError(502, "No fue posible completar la operación de almacenamiento")


@lru_cache(maxsize=1)
def get_storage_service() -> ObjectStorageService:
    config = StorageConfig.from_env()
    return ObjectStorageService(config, crear_cliente(config))
