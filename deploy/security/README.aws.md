# Laboratorio E1 separado de la demo

Estado 18/11/2026: laboratorio desplegado en la VM existente; R0/R1 medidas entre
05:39 y 05:42 UTC, con autorización directa del propietario. No se representan
firmas del grupo ni se utiliza la ventana grupal propuesta sin confirmar.
API: https://e1.3.151.219.131.sslip.io. Permanece en R1 protegido.
Evidencia: `docs/evidence/ciber-e1-aws/`. Tablero y capturas:
https://niftyivy3144.grafana.net/d/inventario-security-e1-aws.

Usar `uv run python -m deploy.security.aws_e1 state`, `R0`, `R1` o `stop`.
Antes de repetir, `authorize --minutes 60` registra una ventana individual nueva.
Las rondas requieren un alcance individual vigente; el archivo privado de esta
práctica tiene su propio vencimiento. Ese vencimiento limita la carga y no
programa el apagado de la VM.

`compose.aws.yml` prepara PostgreSQL, API y Prometheus exclusivos de E1, sin
puertos publicados. Los nombres `e1-api`, `e1-db` y `e1-prometheus` evitan que
Docker resuelva la API compartida hacia el laboratorio. Solo API y Prometheus
comparten la red del gateway; PostgreSQL permanece en la red E1. No se monta
la clave privada del emisor en la API.

Antes de desplegar, comprobar capacidad y disco de la VM existente, guardar copia
del Caddyfile y fijar `SECURITY_API_IMAGE` al digest de la imagen ya verificada.
La imagen y `APP_REVISION` deben corresponder a la misma revisión inmutable.
Preparar una copia separada del proyecto y material privado con
`python -m security.prepare`; nunca reutilizar la clave de negocio del grupo
como clave de prueba adversa. Mantener las claves fuera de Git.

El host previsto `e1.3.151.219.131.sslip.io` debe añadirse al gateway desde
`Caddyfile.aws`, conservando el bloque del servicio compartido. Su Bearer de
consultas es el token de métricas ya configurado en el gateway. Si se usa esa
configuración, fijar ese mismo valor en `prometheus_token` del controlador.
`metrics_token` permanece exclusivo del scrape de la API E1; no confundir
ninguno de ellos con la API key.
Verificar HTTPS, salud, trazas, `up=1`, autenticación y la API grupal antes de
considerar el entorno listo. No basta con levantar Compose.

El primer despliegue queda en `CHAOS_ROUND=none`, política `workload`.
Antes de enviar carga validar la autorización y ventana con
`security.scope.validate_scope`: tres aceptaciones en modo grupal, o autorización
explícita del propietario en el laboratorio individual. No se simulan firmas.
Las rondas usan el mismo perfil, revisión e instancia. Tras las mediciones queda
R1 protegido solo en este laboratorio, sin invalidar la clave del flujo grupal.

El ejecutor usa `security.run_e1`; su comando de parada es
`uv run python -m security.stop_e1` desde la misma raíz y máquina del ejecutor.
STOP cooperativo activa la limpieza acotada del bloque `finally`. Revisar el
resultado y no matar el proceso antes de terminar la limpieza. No detener la
VM ni ejecutar `docker compose down` sobre el proyecto compartido.

Después de las rondas: guardar archivos originales, logs con UTC/trace_id/round,
enlaces reales a runs y capturas del tablero. No convertir pruebas unitarias o
un arranque pasivo en evidencia de una ronda. Las firmas y los resultados
privados permanecen fuera de Git hasta revisar qué evidencia puede publicarse.
