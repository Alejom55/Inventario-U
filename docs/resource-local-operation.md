# Operación local: propuesta de agotamiento de concurrencia

La asignación del fallo c a Inventario-U está pendiente de confirmación del grupo.
El experimento anterior de latencia saliente se conserva. No mezclar ambas evidencias.

## Alcance e hipótesis

Se usan tres réplicas independientes de la misma imagen y un PostgreSQL sintético
aislado. No se inyecta el fallo en la API pública que consume deport-back.
Este experimento local de una API no acredita integración de tres APIs en tres nubes.

**Hipótesis:** con 5 GET `/api/v2/skus` por segundo durante 120 segundos,
cuando seis tareas bloqueantes ocupen concurrencia durante 60 segundos desde t=30,
el p95 será menor de 500 ms y el éxito será al menos 99% en la ventana [30,90).
Cada ventana tiene 300 solicitudes. Timeout de cliente: dos segundos. Se incluyen
errores y timeouts en las mediciones; no se calcula p95 solamente sobre éxitos.

- Estado estable: misma carga, sin fallo.
- R0: seis tareas de fondo comparten y ocupan los seis permisos del pool HTTP.
- R1: misma petición de seis tareas y duración; un bulkhead usa un limiter separado
  y una admisión acotada acepta cuatro tareas, rechazando las otras dos sin cola.

La mitigación protege el tráfico de negocio limitando tareas de fondo; el límite
de seis workers HTTP, la imagen, los datos y el perfil de solicitudes se mantienen.
Las tareas son bloqueos reales de workers AnyIO. No se simula la degradación
devolviendo errores prefabricados desde `/skus`.
Las tres réplicas limitan a 32 las solicitudes simultáneas a `/api/v2/skus`;
ese límite común conserva accesibles métricas y rollback privados durante el fallo.

## Ejecución y reversión

Desde el repositorio:

```powershell
uv run --frozen --group chaos python -m scripts.local_team start
uv run --frozen --group chaos python -m scripts.run_resource_lab
uv run --frozen python -m scripts.local_team status
```

La segunda orden tarda unos siete minutos. Chaos Toolkit ejecuta las rondas
declaradas en `chaos/experiments/resource-concurrency.json`.
Los resultados completos, journals y logs están en `chaos/results/resource-<execution_id>/`.
La comparación legible se guarda en `docs/resource-local-results.md` y Grafana.
Un execution_id identifica la comparación completa; round distingue sus tres ejecuciones.

El interruptor privado `POST /api/v2/admin/resource-fault` acepta solamente
`workers` entero 1..6 y `duration_seconds` entero 1..60. Requiere la clave interna
del laboratorio. `DELETE` libera y verifica los workers; Chaos Toolkit lo ejecuta
como rollback y el generador también lo llama desde `finally`.
Cada worker expira por sí mismo como máximo a los 60 segundos aunque muera el controlador.
La API pública no instala estos controles y su proxy bloquea rutas de administración.

Los puertos 18110/18111/18112 se vinculan únicamente a loopback. La BD de laboratorio
no publica puerto y usa su propio volumen. La carga no usa las bases de GEMA.

Para detener túnel, helper y ambos proyectos propios conservando datos:

```powershell
uv run --frozen python -m scripts.local_team stop
```

## URL, métricas y demostración

Se conserva el Quick Tunnel actual, sin reiniciarlo automáticamente. Al cambiar
la URL, `start` lo anuncia y escribe `deploy/local_team/runtime/URL-CAMBIO.txt`.
El helper compara la sesión cada diez segundos y emite un aviso sonoro local
si cambia. Estos avisos no son mensajes automáticos a los compañeros.

El helper pide a Windows mantener el sistema despierto, sin modificar planes
globales de energía. No garantiza continuidad tras cierre de tapa, reinicio,
corte de corriente o pérdida de internet. Mantener corriente, tapa abierta y Docker.

Prometheus local: `http://127.0.0.1:19190`. Las métricas compartidas están en
`<URL>/shared/metrics` con Bearer independiente de X-Api-Key. Usar
`/shared/prometheus.yml` con `honor_labels: true`. Las series de laboratorio llevan
`track=resource-baseline`, `resource-r0` o `resource-r1`; las series stable/canary
de negocio siguen separadas. Grafana: `/grafana/d/inventory-resource/`.

Los logs JSON de aplicación incluyen `trace_id`, `round` y `execution_id`.
En la API pública es normal `round=none`: el experimento corre en las réplicas.
Grafana observa duración dentro del servidor. El informe de carga mide duración
del cliente e incluye timeouts, por lo que ambas medidas no son intercambiables.
El probe de salud de Chaos Toolkit valida antes/después; el campo `passed` del
informe evalúa el objetivo durante el fallo. Un journal completado no significa
que R0 haya cumplido el objetivo.

`GET /api/v2/skus` es terminal: solo consulta PostgreSQL y devuelve una lista JSON.
No llama a deport-back ni api-fastify. La ruta coordinadora `/integracion` no debe
usarse como dependencia de sus propios proveedores: produciría un ciclo.

Referencias de implementación: [AnyIO workers](https://anyio.readthedocs.io/en/stable/threads.html)
y [experimentos Chaos Toolkit](https://chaostoolkit.org/reference/api/experiment/).
