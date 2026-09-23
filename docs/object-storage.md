# OCI Object Storage

El servicio está en `app/storage/service.py`; las rutas V2 están en
`app/storage/router.py`. El SDK `oci` es una dependencia de runtime y está fijado
en `uv.lock`. No se crea otro proyecto ni se cambia la integración externa.

## Configuración

Define las variables en el entorno del proceso:

```dotenv
OCI_NAMESPACE=<namespace de tu tenancy>
OCI_BUCKET_NAME=<nombre del bucket>
OCI_REGION=sa-bogota-1
OCI_AUTH_MODE=instance_principals
TEAM_API_KEY=<clave compartida del equipo>
```

Los marcadores son ejemplos, no valores utilizables. `.env.example` conserva
vacíos los valores que debes proporcionar. Si usas un archivo `.env`, cárgalo
explícitamente al iniciar el servidor:

```powershell
uv sync --frozen
uv run uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

La aplicación continúa necesitando su `DATABASE_URL` habitual para el startup.
Storage no utiliza PostgreSQL. El Docker Compose actual no pasa automáticamente
estas variables: debes inyectarlas en el entorno del contenedor mediante el
mecanismo de despliegue existente. No se modifican Docker, OKE ni pipelines.

Autenticación del SDK:

- `instance_principals`: opción predeterminada para una instancia Compute con
  identidad y políticas IAM configuradas. No necesita claves de usuario.
- `resource_principals`: usa el signer oficial y las variables
  `OCI_RESOURCE_PRINCIPAL_*` suministradas por un recurso OCI compatible.
- `config_file`: alternativa local. Define `OCI_CONFIG_FILE` (por defecto
  `~/.oci/config`) y `OCI_CONFIG_PROFILE` (por defecto `DEFAULT`). El perfil OCI
  estándar contiene `user`, `tenancy`, `fingerprint`, `key_file` y `region`.
  Guarda archivo y clave privada fuera del repositorio. `OCI_REGION` prevalece
  sobre la región del perfil.

Los modos son explícitos: no se intenta una identidad distinta si falla el modo
seleccionado. OKE Workload Identity utiliza un signer específico diferente;
no está habilitado por esta implementación. No presupongas que un pod OKE tiene
Instance Principals o Resource Principals disponibles. La identidad del entorno
debe comprobarse antes del despliegue, que queda fuera de esta tarea.

El cliente se inicializa al primer uso y se reutiliza. Reinicia la aplicación
después de cambiar variables. Sin configuración OCI, health sigue disponible;
las operaciones de storage responden `503`. El cliente usa 5 segundos de timeout
de conexión y 30 de lectura, sin reintentos automáticos de Object Storage. Estos
límites no constituyen un plazo total para obtener o renovar credenciales.

## Crear el bucket manualmente

1. Abre la consola OCI y selecciona la región que usarás en `OCI_REGION`.
2. En **Storage → Object Storage & Archive Storage → Buckets**, selecciona el
   compartment adecuado y pulsa **Create bucket**.
3. Elige un nombre, tier **Standard**, acceso **privado** y cifrado administrado
   por Oracle. Versioning es opcional; permite conservar versiones sobrescritas.
4. Copia el nombre a `OCI_BUCKET_NAME` y el Object Storage Namespace mostrado
   por OCI a `OCI_NAMESPACE`. El namespace no es el OCID del compartment.
5. Configura IAM para que la identidad de la aplicación pueda crear, sobrescribir
   y leer objetos en ese bucket. La aplicación no necesita crear buckets.

Ejemplo de política para un dynamic group de instancias, sustituyendo todos los
marcadores y limitando al bucket y las operaciones necesarias:

```text
Allow dynamic-group <grupo> to manage objects in compartment <compartment> where all {target.bucket.name='<bucket>', any {request.permission='OBJECT_CREATE', request.permission='OBJECT_OVERWRITE', request.permission='OBJECT_READ'}}
```

Para desarrollo local, concede los mismos permisos al grupo IAM del usuario del
perfil. La configuración de la identidad y la creación del bucket son manuales;
el código no cambia políticas ni crea recursos. No se necesita una carpeta real
`flujos`: es un prefijo del nombre del objeto.

Referencias oficiales:
[crear buckets](https://docs.oracle.com/en-us/iaas/Content/Object/Tasks/managingbuckets_topic-To_create_a_bucket.htm),
[signers del SDK](https://docs.oracle.com/en-us/iaas/tools/python/latest/api/signing.html),
[permisos Object Storage](https://docs.oracle.com/en-us/iaas/Content/Identity/Reference/objectstoragepolicyreference.htm).

## Guardar y recuperar desde PowerShell

Con el servidor iniciado, configura la misma clave de la aplicación en
`$env:TEAM_API_KEY` para esta terminal. Si el servidor deja esa variable vacía,
storage queda abierto igual que las demás rutas funcionales existentes.

```powershell
$headers = @{
    'X-Api-Key' = $env:TEAM_API_KEY
    'X-Trace-Id' = 'abc-123'
}
$body = @{
    trace_id = 'abc-123'
    data = @{
        trace_id = 'abc-123'
        inventario = @{ ciudad = 'Bogotá' }
        deportista = @{}
        articulo = @{}
    }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v2/storage' `
    -Headers $headers -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))

Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/api/v2/storage/abc-123' `
    -Headers $headers
```

POST responde `201` con `trace_id`, `object_name`, `bucket` y `status: stored`.
Guarda exactamente `data`, como UTF-8 y `application/json`, en
`flujos/abc-123.json`. Repetir el trace sobrescribe ese objeto; sin versioning no
se conserva el contenido anterior. GET devuelve el objeto JSON guardado.

El trace del POST se toma de `X-Trace-Id`; si falta, se usa `trace_id` del cuerpo.
Si ambos faltan, se reutiliza el UUID del middleware existente. Si ambos están
presentes deben coincidir. En una escritura exitosa, el encabezado de respuesta
y el resultado contienen el mismo trace. Se aceptan 1–128 caracteres ASCII:
primero una letra o dígito, después letras, dígitos, guiones o guiones bajos.
No se sanea silenciosamente un ID ni se aceptan rutas o extensiones.

En GET, el ID de la ruta identifica el objeto; `X-Trace-Id` identifica la petición
actual y conserva el comportamiento del middleware. Los errores de lectura
registran ambas referencias mediante los logs del servicio y de la ruta.

Errores públicos:

| Estado | Situación |
| --- | --- |
| 401 | API key ausente o incorrecta cuando `TEAM_API_KEY` está configurada |
| 404 | OCI devuelve `ObjectNotFound` durante una lectura |
| 422 | Trace inválido, traces conflictivos o contenido no serializable |
| 502 | Fallo de red/SDK o contenido remoto inválido |
| 503 | Configuración, autenticación, permisos, bucket inexistente o indisponibilidad OCI |
| 504 | Timeout |

OCI puede ocultar la existencia de recursos por permisos. Un `404` ambiguo de
OCI no se presenta como objeto ausente. No se publican mensajes originales,
credenciales ni cabeceras del SDK; los logs de error incluyen `trace_id`.

## Reutilización desde integración

`GET /api/v2/integracion` no escribe en OCI. Cuando se decida habilitarlo, puede
pasarse su respuesta acumulada directamente al servicio existente:

```python
from app.storage.service import get_storage_service

# Solo en un flujo que decida explícitamente persistir la respuesta:
resultado = get_storage_service().guardar_json(respuesta["trace_id"], respuesta)
```

## Pruebas

Pruebas de storage sin credenciales, red OCI ni PostgreSQL:

```powershell
uv run --frozen pytest tests/storage -o addopts='' --cov=app.storage --cov-report=term-missing --cov-fail-under=85
```

Suite completa, con `TEST_DATABASE_URL` apuntando a una base exclusiva de pruebas:

```powershell
uv run --frozen pytest
```

El fixture existente vacía tablas de esa base en cada prueba de inventario.
Nunca apuntes `TEST_DATABASE_URL` a desarrollo o producción.
