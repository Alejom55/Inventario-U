# Inventario-U compartido desde este PC

Práctica local con base sintética independiente (`inventario-team-local`).
API con CRUD, Grafana Viewer y métricas protegidas. No sustituye las tres nubes
ni las rondas formales del trabajo de Caos.

Desde la raíz del repositorio, con Docker Desktop encendido:

```powershell
uv run --frozen python -m scripts.local_team start
uv run --frozen python -m scripts.local_team status
uv run --frozen python -m scripts.local_team demo
uv run --frozen python -m scripts.local_team stop
```

`start` construye la imagen, conserva credenciales existentes, crea/reutiliza
el usuario Viewer y datos de ejemplo, y abre Cloudflare Quick Tunnel usando
el ejecutable instalado. El proceso queda en segundo plano sin ventana.
La URL solo se anuncia después de comprobar HTTPS y la revisión de la API.
Una URL nueva actualiza la guía de Grafana y todos los archivos compartibles.

`stop` comprueba PID, fecha de creación y ejecutable antes de detener únicamente
el túnel de esta práctica; detiene sus contenedores y conserva los volúmenes.
No detiene GEMA, no inicia OCI y no modifica el entorno canary anterior.
El PC debe permanecer encendido y sin suspenderse para que el equipo tenga acceso.

Los puertos solo escuchan en loopback: operador `18100`, acceso compartido
`18180`, Prometheus `19190`. PostgreSQL no publica puerto al host.
En la URL pública solo se exponen el CRUD V2, inventario GET/QUERY, archivos de
integración, métricas federadas de inventario y Grafana con login Viewer.
La clave para compañeros es distinta de la clave interna de operación.
El token de métricas es distinto de ambas. Los controles de fallos, coordinador,
Object Storage y administración no están disponibles en la puerta pública.

## Entregar a los compañeros

El comando imprime la URL. El archivo privado
`runtime/credenciales-companeros.txt` contiene exclusivamente las credenciales
que puedes compartir con el grupo. No enviarlo a repositorios ni paneles.
La contraseña de administrador y la clave interna permanecen en
`runtime/settings.json`; conserva ese archivo para futuros reinicios.
Si se pierde y existen datos, el arranque se detiene en vez de rotar la clave
de PostgreSQL y dejar inaccesible el volumen.

Los archivos sin secretos están en `runtime/exports/` y se pueden descargar
desde `/shared/guia.md`, `/shared/contrato.json`, `/shared/postman.json`,
`/shared/prometheus.yml` y `/shared/dashboard.json`.
La guía y el prompt para sus IA están dentro del tablero `inventory-team`.
Sus Prometheus deben montar el archivo privado del token indicado en la
plantilla; al importar el dashboard, elegir su propio datasource Prometheus.

Los datos son compartidos y modificables: crear pruebas con códigos únicos.
Los IDs de demostración se informan en la guía. No se restablece su stock al
reiniciar, y un usuario puede eliminarlos mediante el CRUD.

## Validación

```powershell
uv run --frozen python -m scripts.verify_local_team
```

Verifica el CRUD real y limpia únicamente sus entidades temporales, la
compatibilidad QUERY, trazas por ambas puertas, aislamiento de claves, bloqueo
de controles, métricas reales, Viewer y consulta del datasource de Grafana.
Los resultados sin credenciales quedan en `runtime/verification.json`.
El perfil k6 formal no se modifica; `demo` solo envía 60 peticiones reales para
ver actividad inicial en los tableros.

La URL de Quick Tunnel cambia al reiniciarlo y no ofrece garantía de disponibilidad:
[documentación de Cloudflare](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
