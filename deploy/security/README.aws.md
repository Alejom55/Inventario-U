# Laboratorio E1 separado de la demo

Estado: configuración preparada y comprobada offline. **No desplegado; no hay rondas oficiales.**
La ventana propuesta de 18/11/2026, 15:00-16:00 UTC sigue sin confirmar por el grupo.

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
configuración, fijar ese mismo valor en el campo `metrics_token` del controlador
y en la configuración de recolección E1; no confundirlo con la API key.
Verificar HTTPS, salud, trazas, `up=1`, autenticación y la API grupal antes de
considerar el entorno listo. No basta con levantar Compose.

Mantener `CHAOS_ROUND=none` y política `workload` en espera. No cambiar a R0,
enviar intentos adversos ni publicar cifras hasta validar las tres aceptaciones
y la ventana con `security.scope.validate_scope`. Las rondas oficiales deben
usar el mismo perfil, revisión e instancia. La política R1 se aplica únicamente
a este laboratorio, sin invalidar la API key utilizada por los compañeros.

El ejecutor usa `security.run_e1`; su comando de parada es
`uv run python -m security.stop_e1` desde la misma raíz y máquina del ejecutor.
STOP cooperativo activa la limpieza acotada del bloque `finally`. Revisar el
resultado y no matar el proceso antes de terminar la limpieza. No detener la
VM ni ejecutar `docker compose down` sobre el proyecto compartido.

Después de las rondas: guardar archivos originales, logs con UTC/trace_id/round,
enlaces reales a runs y capturas del tablero. No convertir pruebas unitarias o
un arranque pasivo en evidencia de una ronda. Las firmas y los resultados
privados permanecen fuera de Git hasta revisar qué evidencia puede publicarse.
