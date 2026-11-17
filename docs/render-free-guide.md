# Inventario-U: ejecución real en Render Free

API: https://inventario-chaos-free.onrender.com
GET /api/v2/skus es terminal: consulta PostgreSQL, sin invocar a los compañeros.
Autenticación de negocio: X-Api-Key. Propagar X-Trace-Id.
Datasource Prometheus: https://inventario-chaos-prom-free.onrender.com; header Authorization: Bearer <token privado>.
No colocar claves en paneles, repositorios ni mensajes del grupo.

**Única métrica objetivo: éxito del cliente ≥99% durante el fallo.**
Guardarraíl separado: p95 del cliente <500 ms, incluyendo errores y timeouts.
Perfil: 5 peticiones/s, 120 s; fallo desde t=30 durante 60 s; timeout 2 s.
Estado estable, R0 y R1 usan la misma versión e instancia de la API y los mismos datos.
R0 comparte los seis permisos HTTP con seis tareas de fondo. R1 usa bulkhead y
admisión máxima de cuatro tareas de fondo, rechazando dos sin cola.
El interruptor requiere una clave administrativa distinta y tiene expiración de 60 s.

Las mediciones son de una API real en Render; no acreditan por sí solas el flujo
integrado de tres APIs ni Chaos Mesh/GKE. El grupo debe aceptar Render en lugar de OCI.
Aquí R0/R1 son rondas de caos; no son las versiones stable/canary del ejercicio anterior.

| Ronda | Éxito % | p95 ms | Variación p95 % | Objetivo | Guardarraíl |
|---|---:|---:|---:|---|---|
| BASELINE | 100.000 | 317.210 | 0.00 | cumple | cumple |
| R0 | 0.000 | 2015.747 | 535.46 | refutada | no cumple |
| R1 | 100.000 | 295.692 | -6.78 | cumple | cumple |

Generador: GitHub-hosted Ubuntu. Las latencias incluyen su ruta de red hacia Render. No comparar directamente con las ejecuciones desde el PC del operador como si tuvieran el mismo origen.

Execution ID: `11e3e0fc15d34f26a86d5946b2c80351`

Revisión: `6e29c9addfa6d7e583c082ce5b001f202b811f85`

Deployment: `dep-dbubbf08v5cc738j7fng`

**BASELINE**: 2026-11-17T20:18:45.279372+00:00 a 2026-11-17T20:20:45.233468+00:00; trace_id `3d70fc84119a4881aa57544c6df3ce00`. Inyección: sin fallo; reversión: verificada al finalizar.

**R0**: 2026-11-17T20:20:46.189816+00:00 a 2026-11-17T20:22:46.182288+00:00; trace_id `9277389fb1d849f49b43dfdac8bd8869`. Inyección: 2026-11-17T20:21:16.287124+00:00; reversión: 2026-11-17T20:22:16.377689+00:00.

**R1**: 2026-11-17T20:22:46.913061+00:00 a 2026-11-17T20:24:46.839807+00:00; trace_id `2182c092db7e4ff0885c19b3a61ed585`. Inyección: 2026-11-17T20:23:17.024073+00:00; reversión: 2026-11-17T20:24:17.130349+00:00.

Prometheus tiene almacenamiento temporal. Descargar el informe; un reinicio puede perder las series. Cero tráfico sin peticiones es normal. Los indicadores de éxito/p95 del cliente se publican al terminar cada ronda, a partir de las muestras reales del generador.

## Postman y conexión del equipo

Método GET, URL https://inventario-chaos-free.onrender.com/api/v2/skus. Header X-Api-Key: {{inventario_api_key}} y X-Trace-Id: equipo-{{$guid}}. Usar variables de entorno; credenciales por privado. IDs sintéticos: SKU 1 y almacén 1. Consulta GET /api/v2/inventario?sku_id=1&almacen_id=1, respuesta resultados[]. No llamar /integracion desde deport-back: causaría un ciclo.

En Grafana Cloud común, crear datasource tipo Prometheus con URL https://inventario-chaos-prom-free.onrender.com, método POST y header seguro Authorization: Bearer <token privado de métricas>. Importar docs/render-free-dashboard.json y seleccionar ese datasource.

## Sustentación desde Actions

Abrir Actions > Validacion local de caos > Run workflow > Branch feat/render-free > Run workflow. El job render_free ejecuta las tres rondas sin crear infraestructura. R0 degrada el servicio durante 60 s: coordinar la ventana del grupo. Los resultados se descargan en el artefacto render-free-<run_id>.

Ejecución verificada: https://github.com/Alejom55/Inventario-U/actions/runs/44167802835
