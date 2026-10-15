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

## Ejecución real en OCI: 14 de octubre de 2026 (Bogotá)

**Resultado: despliegue y pruebas reales correctos. VM detenida después de las pruebas.**

- Bootstrap aplicado: bucket privado y versionado `inventario-u-tfstate` y backend OCI.
- A1 no tenía capacidad en los tres dominios de fallo de Bogotá. Se autorizó
  expresamente E5 de 1 OCPU y 6 GB, con máximo USD 2 y apagado tras las pruebas.
- Se añadió selección explícita A1/E5; A1 continúa siendo el valor predeterminado.
  Formato, validación y los **5 casos Terraform simulados** pasaron tras el cambio.
- GitHub environment `oci-demo` configurado con secrets cifrados y variables.
  La clave privada local está fuera del repositorio. No se incluyen secretos en evidencias.
- [Pipeline de despliegue exitoso](https://github.com/Alejom55/Inventario-U/actions/runs/38666265881):
  validación y despliegue correctos; duración total 8 min 32 s.
- Revisión desplegada: `4e8d5d15ff5e6913f62592cc93ce94a19a7bf744`.
  La release v2.1.0 incorpora después documentación y evidencias, sin cambiar la aplicación.
- Terraform administra 16 recursos en el módulo principal y el bucket bootstrap
  por separado. Cloud-init terminó, Docker arrancó y OCI Run Command instaló la API.
- URL durante las pruebas: `http://157.137.207.154:8000`, restringida por CIDR.
- Prueba externa: health 200, petición sin clave 401, SKU y almacén creados,
  entrada de 10 unidades y consulta de inventario con stock 10.
- Object Storage real: escritura, lectura exacta del JSON y listado correctos.
- Swagger fue accesible. API y PostgreSQL se ejecutaron en Docker dentro de Compute.
- Se solicitó SOFTSTOP y se confirmó **STOPPED** con OCI SDK y consola.
  La API queda fuera de servicio mientras la instancia está detenida.

Los JSON y capturas están en [evidencias/README.md](evidencias/README.md).
Los horarios UTC del JSON corresponden a la noche del 14 de octubre en Bogotá.

## Alcance y límites

Los servicios usados son Compute, VCN, Object Storage y Vault. PostgreSQL 16 es
**autogestionado en Compute**, no una base de datos administrada de OCI.
Las pruebas locales/simuladas anteriores y la ejecución real se documentan por separado.

La VM estuvo encendida aproximadamente 26 minutos. El costo de cómputo estimado
con la tarifa usada para autorizar la demo (USD 0,042/h) es inferior a USD 0,02;
esto no es una factura ni un total confirmado de la cuenta. El almacenamiento y
otros recursos permanecen hasta su eliminación y pueden tener costo.

La consola mostró **Free Trial ended** y advirtió que recursos no Always Free
pueden eliminarse. No se garantiza poder reactivar o conservar E5. No se cambió
el plan de la cuenta. Antes de la defensa se debe revisar capacidad/elegibilidad,
reactivar o redesplegar con presupuesto autorizado y comprobar la IP permitida.

El método de destrucción está implementado y documentado; no se ejecutó contra
esta demo porque se conservaron recursos para la defensa. La demo HTTP usa datos
de prueba; no sustituye HTTPS para producción. Las integraciones con compañeros
necesitan sus URLs/IDs/clave acordados. La sustentación y la subida a UVirtual
son pasos que realiza el estudiante.
