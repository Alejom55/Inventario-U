# Inventario-U: práctica gratuita en Render

La rama `feat/render-free` conserva los despliegues anteriores y crea una API,
un Prometheus autenticado y un PostgreSQL sintético separados. Todas las solicitudes
de creación especifican `plan: free`; no se aceptan planes de pago ni discos extra.

Las credenciales y IDs operativos están exclusivamente en `deploy/render/runtime/`,
excluido de Git. La clave de Render nunca se envía a la aplicación desplegada.
Negocio, control de fallos y métricas tienen claves distintas.

La API ejecuta BASELINE/R0/R1 secuencialmente en la misma versión e instancia.
El health check asíncrono permanece disponible al agotarse el pool de negocio.
Los indicadores del cliente se publican al terminar cada ronda; los registros crudos
y journals permanecen en `chaos/results/render-<execution_id>/`, ignorado por Git.
El informe versionado solo incluye métricas y trazabilidad sin credenciales.

```powershell
uv run --frozen python -m scripts.render_free status
uv run --frozen --group chaos python -m scripts.run_render_resource
uv run --frozen python -m scripts.render_free stop
uv run --frozen python -m scripts.render_free start
```

`start` reanuda los dos servicios nuevos y programa una práctica de dos horas.
`stop` suspende únicamente esos servicios; conserva el PostgreSQL gratuito y sus
datos sintéticos. No toca Inventario-U ni inventario-dev-api anteriores.
El guard externo mantiene Windows despierto y suspende ambos servicios al vencer
la ventana. Requiere que este PC tenga corriente y conexión; cerrar la tapa o apagar
el equipo puede impedir esa llamada. Los recursos siguen en plan Free.

Render puede suspender instancias tras 15 minutos sin tráfico. Despertarlas puede
tardar aproximadamente un minuto; esperar salud y revisar identidad antes de medir.
PostgreSQL Free vence a los 30 días. Prometheus usa disco efímero y retiene tres horas;
exportar evidencias antes de suspender. No se garantiza retención tras reinicios.

Este despliegue es una API en una nube real. No equivale a completar el flujo de
tres APIs ni Chaos Mesh/GKE. El equipo debe aceptar Render como sustituto de OCI.
No renombrar evidencia local previa como si hubiera sido ejecutada en nube.

Para Grafana Cloud, usar la URL del Prometheus nuevo como datasource, método POST
y header seguro `Authorization: Bearer <token privado de métricas>`. Importar el
tablero descargable generado en `docs/render-free-dashboard.json` y seleccionar
esa fuente. Nunca colocar tokens en paneles ni en el grupo.

## Botón Run workflow

En GitHub, iniciar sesión como Alejom55 y abrir Actions > **Validacion local de caos**.
Pulsar **Run workflow**, seleccionar **feat/render-free** y ejecutar. El job
`render_free` realiza BASELINE/R0/R1 desde un runner GitHub; `main` conserva el
comportamiento offline anterior. No se fusiona la rama ni se modifican los servicios
Inventario-U e inventario-dev-api existentes.

El repositorio tiene dos secretos cifrados exclusivos de la API sintética:
`RENDER_CHAOS_API_KEY` y `RENDER_CHAOS_ADMIN_KEY`. No contiene la clave de cuenta Render,
la conexión PostgreSQL ni el token de métricas. Los artefactos pasan un escaneo de claves.
El gate exige estado estable correcto, degradación demostrada en R0 y recuperación
de éxito >=99% más el guardarraíl p95 <500 ms en R1. El fracaso esperado de R0 no
hace fallar el job. Descargar el artefacto `render-free-<run_id>` para revisar muestras
crudas, journals, UTC, execution_id y trace_id.

Se conservan por separado las ejecuciones iniciales desde el PC. Sus latencias no
son intercambiables con las de un runner GitHub; la comparación de rondas utiliza
un mismo origen, perfil, versión de aplicación e instancia.

Validación final: 292 pruebas locales aprobadas, cobertura 94,04%; el subconjunto
offline del workflow pasa 173 pruebas sin base de datos. La ejecución manual
[44167802835](https://github.com/Alejom55/Inventario-U/actions/runs/44167802835)
completó las tres rondas reales. La verificación HTTPS posterior confirmó CRUD,
compatibilidad GET/QUERY, autenticación, trazas y consultas de los paneles.
