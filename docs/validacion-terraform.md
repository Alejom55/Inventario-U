# Validación de la entrega 3

Fecha: 14 de octubre de 2026. Entorno local Windows, Docker Desktop y Python 3.13.

## Comprobado antes del push

- Terraform 1.16.5: formato, `init -backend=false` y `validate` correctos.
- Proveedores fijados: OCI 7.32.0 y Random 3.9.1; checksums Windows/Linux.
- `terraform test`: 4 casos correctos, con proveedores **simulados**.
- Módulo bootstrap: inicialización y validación correctas.
- Suite Python: 118 pruebas correctas; cobertura de `app`: **93,22 %**, superior
  al mínimo 85 %. PostgreSQL 16 aislado en Docker; no se usó una base del usuario.
- actionlint 1.7.12: los dos workflows nuevos sin errores.
- `bash -n`: scripts de despliegue, bootstrap y destrucción sin errores de sintaxis.
- Imagen Docker construida para Linux amd64 y Linux arm64 (arquitectura de A1).
- Compose OCI arrancó API y PostgreSQL y ambos alcanzaron estado healthy.
- API local: health correcto; sin clave devuelve 401; creación de SKU correcta;
  el SKU continúa disponible después de reiniciar el contenedor de la API.
- PostgreSQL no publica ningún puerto en el host.

## Pendiente de comprobar en OCI

No se ha ejecutado `terraform apply` real. La sesión de la consola no aporta
credenciales al SDK ni al pipeline. Faltan API key OCI, bucket de estado remoto
y secrets/variables de GitHub para el despliegue.

No se han comprobado disponibilidad de A1 en Bogotá, cuotas restantes de toda la
tenancy, instalación completa de cloud-init en Oracle Linux, propagación IAM,
lectura de Vault desde la VM ni prueba de Object Storage contra una cuenta real.
Las pruebas Python de OCI utilizan mocks. El pipeline ejecutará un smoke real
contra PostgreSQL y Object Storage y fallará si no se completa.

Las integraciones externas necesitan URLs/IDs/clave acordados con los compañeros.
La demo HTTP está restringida por CIDR y no sustituye HTTPS para uso real.
Hay advertencias de deprecación preexistentes de FastAPI/Starlette; no se
cambiaron dependencias ni rutas funcionales para ocultarlas.
