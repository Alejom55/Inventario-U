# Operación del despliegue canary en OCI

Inventario-U ejecuta stable v2 y canary v3 en contenedores separados de una VM
OCI Compute. Nginx distribuye peticiones hacia ambos tracks. Prometheus recoge
métricas cada cinco segundos y Grafana las compara. El controlador decide con
la política versionada en `deploy/canary/policy.json`.

## Requisitos y acceso

Se reutilizan la VM, red, volumen PostgreSQL, Vault, claves e IAM de la entrega
anterior. El workflow `Canary en OCI` no aplica Terraform ni crea infraestructura.
La VM debe estar encendida y tener operativo Compute Instance Run Command.
Una cuenta cuya prueba gratuita terminó debe verificar elegibilidad y coste
antes de encender una forma E5. No cambiar automáticamente a una forma de pago.

El entorno GitHub `oci-demo` conserva los secrets `OCI_TENANCY_OCID`,
`OCI_USER_OCID`, `OCI_FINGERPRINT` y `OCI_PRIVATE_KEY`. Añadir las variables
`OCI_INSTANCE_ID`, `OCI_COMPARTMENT_ID` y `OCI_REGION` con los identificadores
del despliegue existente. No publicar claves, contraseñas ni archivos `.env`.

La entrada pública sigue siendo el puerto 8000 limitado por `api_allowed_cidr`.
PostgreSQL y las APIs no publican puertos. Prometheus solo escucha en loopback
del host y Grafana requiere inicio de sesión en `/grafana/`. Esta demo conserva
el HTTP de la entrega anterior: acceder desde una red de confianza y mantener
el CIDR restringido; para uso externo habitual añadir terminación TLS antes de
transmitir claves. Las cabeceras de identidad provienen del proceso de API.

## Rutas y selección

| Ruta o cabecera | Comportamiento |
| --- | --- |
| `/api/v2/*` | Siempre stable y contrato v2 |
| `/api/v3/*` | Siempre canary y clave `X-Api-Key` obligatoria en el proxy |
| `/api/live/*` | Distribución pública según la etapa; conserva método y cuerpo |
| `X-Canary: true` y clave válida | Prueba interna de canary incluso con público en 0 |
| `X-Canary: baseline` y clave válida | Prueba comparable de stable incluso al 100 |
| `/metrics` público | 404; el scraping usa la red interna de Docker |

Cada respuesta de API lleva `X-App-Version`, `X-App-Track`, `X-App-Revision`.
En respuestas generadas por el proxy, como un 403 de acceso a preview, no hubo
instancia de API y no se atribuye falsamente un track.

No se fijan sesiones. Nginx aplica `split_clients` sobre un identificador aleatorio
por petición. Con pocas peticiones, los porcentajes pueden fluctuar. La evidencia
de reparto excluye las sondas forzadas de comparación, que sí forman parte de las
métricas de carga de cada versión.

## Etapas y decisión

| Etapa | Público canary | Horneado mínimo | Tiempo máximo |
| --- | --- | --- | --- |
| 0 | 0 por ciento | 60 segundos | 300 segundos |
| 1 | 10 por ciento | 120 segundos | 300 segundos |
| 2 | 50 por ciento | 120 segundos | 300 segundos |
| 3 | 100 por ciento | 120 segundos | 300 segundos |

La ventana móvil de análisis dura 60 segundos. Antes de promover se requieren
al menos 1000 peticiones por track en esa ventana, 500 peticiones públicas por
etapa y una distribución compatible con el porcentaje esperado. Para 10 y 50
se admite cuatro errores estándar más un punto porcentual; para 0 y 100 no
se admite ningún track público distinto del esperado. Son umbrales de una demo
controlada, no una garantía de independencia estadística de usuarios reales.
Con cero errores en 1000 solicitudes, la regla aproximada de tres sitúa el
límite superior de error al 95 por ciento cerca de 0,3 por ciento.

El generador realiza consultas `QUERY /api/live/inventario/query` con el mismo
cuerpo y autenticación, hasta 80 RPS y doce trabajadores por defecto. La mitad
genera una muestra pública y la otra mitad compensa el reparto para equilibrar
la carga total esperada en ambos tracks, incluso durante 0 y 100. Por ejemplo,
en 0 las sondas van a canary y el público a stable; en 50 las sondas se dividen
por igual. No modifica inventario ni llama integraciones.

SLO de ambos tracks: 5xx y 4xx no superiores a 1 por ciento, p95 hasta 500 ms,
p99 hasta un segundo, CPU hasta 0,85 de un core y memoria de proceso hasta
80 por ciento de 512 MiB. Cada API tiene límite de un core y 512 MiB.
El indicador de CPU/memoria es del proceso de API; no incluye page cache ni
otros procesos del contenedor. El tablero identifica este alcance.
Canary no puede superar p95 de baseline multiplicado por 1,5 más 50 ms ni
su tasa 5xx por más de 0,5 puntos porcentuales. Las consultas de negocio
completadas deben cubrir al menos 99 por ciento de la muestra.

Se promueve solo con muestra, horneado y SLO completos. Falta de métricas,
muestra insuficiente o baseline degradado pausarán la etapa. Una regresión
de canary aborta desde 100 peticiones por track; canary caído aborta sin esperar
esa muestra. Pausar no significa aprobar: al vencer 300 segundos se vuelve a 0.
La puerta consulta cada diez segundos; el aborto es inmediato al decidir,
pero existe ese intervalo de detección y la ventana de observación.

## Instalación y ejecución

Publicar primero la rama y revisar el código. Desde GitHub Actions, seleccionar
`Canary en OCI`, la misma referencia de Git para todas las operaciones y:

1. `install`: construye una imagen, resuelve su ID SHA256, guarda un `pg_dump`,
   inicia ambos tracks y reemplaza el listener anterior dejando canary en 0.
2. `promote`: ejecuta etapas 0, 10, 50 y 100 con puerta automática.
3. `regression`: vuelve a 0, valida baseline e inyecta 50 por ciento de errores
   en canary durante la etapa 10. Debe abortar y verificar 30 consultas stable.
4. `rollback`: fuerza 0 y verifica esas 30 consultas, sin alterar datos.

La instalación actualiza el archivo del punto de entrada privilegiado existente;
no amplía sudo a una shell genérica. La imagen de aplicación se construye una
sola vez por instalación. El archivo privado `/opt/inventario/canary.env`
referencia `sha256:...`; los pasos de promoción no reconstruyen ni actualizan
contenedores. Ambos tracks usan ese artefacto con configuración explícita y
contratos diferentes. La promoción cambia únicamente la configuración del proxy.

Los contenedores de plataforma están versionados por tag; el artefacto de API,
que atraviesa las etapas, está fijado por su ID de contenido local. Esa identidad
es portable al registro mediante un push por digest si se necesitan varias VMs.

La contraseña de Grafana queda en `/opt/inventario/grafana.password` con permisos
600. Usuario `admin`. No imprimirla en logs ni guardarla en el repositorio.
Tablero: `/grafana/d/inventory-canary/`. La API key se obtiene del mecanismo
Vault existente y se conserva en archivos privados del host.

Las decisiones se guardan en `deploy/canary/evidence/rollout.jsonl` dentro del
checkout de la VM. Incluyen fecha UTC, revisión, imagen, política, percentiles,
muestras, reparto y resultado del rollback, sin credenciales. Conservar una
copia sanitizada junto a capturas de la nube para documentar la ejecución real.
Los archivos `docs/evidencias/` anteriores corresponden a Terraform v2 y no
prueban este despliegue canary.

## Compatibilidad de datos y rollback

La expansión v3 añade `estado_stock` y `unidades_reponer` a cada resultado de
inventario. No requiere columnas nuevas, reescrituras ni una cola o caché nueva.
Stable mantiene los campos anteriores y todos los movimientos usan las mismas
tablas y validaciones. Los objetos conservan el prefijo `flujos/` y esquema JSON.
El proceso canary no ejecuta DDL al arrancar. El proceso stable conserva el
bootstrap anterior; no se añade ninguna migración destructiva en esta entrega.

La fase Contract queda aplazada hasta retirar v2 y vencer la ventana de rollback.
Si se ampliase persistencia, añadir primero campos opcionales y lectores que
toleren ausencia; rellenar datos después y eliminar solo en una entrega posterior.
En esta implementación la expansión está en la respuesta, por lo que no hace
falta una migración para demostrar compatibilidad.

Rollback cambia el reparto público a 0 sin borrar volúmenes, revertir tablas ni
deshacer movimientos aceptados. El backup previo es recuperación de desastre,
no el mecanismo del rollback. La inyección afecta solo lecturas canary. Las
sondas internas continúan pudiendo llegar a canary con clave aun en 0.

## Ensayo local aislado

Con Docker Desktop operativo, desde el repositorio:

```powershell
uv sync --frozen --group dev
docker build -t inventario-canary:local .
uv run python -m deploy.canary.prepare_local
docker compose --env-file deploy/canary/runtime/local.env -f deploy/canary/compose.yml up -d --wait
uv run python -m deploy.canary.rollout promote --env-file deploy/canary/runtime/local.env --base-url http://127.0.0.1:18000 --prometheus http://127.0.0.1:19090
uv run python -m deploy.canary.rollout regression --env-file deploy/canary/runtime/local.env --base-url http://127.0.0.1:18000 --prometheus http://127.0.0.1:19090
```

El proyecto local `inventario-canary-local` usa volúmenes propios y puertos 18000
y 19090. Los secretos se generan en `runtime/local.env`, excluido de Git.
Si ese archivo existe se reutiliza; no rotar la contraseña de una base existente
borrando el archivo. Detener con el mismo comando Compose seguido de `stop`.

## Límites y referencias

Esta arquitectura académica comparte una VM y una base. Canary reduce el impacto
de una regresión de API; no ofrece tolerancia a caída del host ni aislamiento
completo de recursos. Las peticiones en curso pueden finalizar durante un cambio
de etapa. No se usa una actualización Terraform para reactivar la VM ni se
elimina infraestructura desde el workflow canary.

Referencias oficiales:

- Nginx split clients: https://nginx.org/en/docs/http/ngx_http_split_clients_module.html
- Nginx recarga: https://nginx.org/en/docs/control.html
- Prometheus histogramas: https://prometheus.io/docs/practices/histograms/
- Prometheus consultas: https://prometheus.io/docs/prometheus/latest/querying/functions/
- OCI Run Command: https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm
