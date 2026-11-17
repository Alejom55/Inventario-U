# Inventario-U: evidencia local de agotamiento de concurrencia

Asignación c propuesta; el grupo debe confirmar el cambio desde latencia saliente.
Réplica local aislada; no demuestra tres APIs en tres nubes. La API compartida no recibió este fallo.

Hipótesis: con 5 GET /api/v2/skus por segundo durante 120 s, al solicitar 6 tareas bloqueantes durante 60 s desde t=30, p95 <500 ms y éxito >=99% en la ventana [30,90).
Carga de llegada constante: 600 peticiones, timeout 2 s; 300 muestras en cada ventana. Las respuestas fallidas y timeouts se incluyen en p95.
R0: las tareas ocupan los 6 permisos del pool HTTP. R1: bulkhead con limiter separado y admisión máxima de 4 tareas de fondo sin cola; se rechazan 2. Misma solicitud de fallo, distinta protección.
La hipótesis de disponibilidad de Chaos Toolkit verifica antes/después; passed en la tabla evalúa el objetivo DURANTE el fallo.

| Medición | p95 ms | Error % | Variación p95 vs estable % | Objetivo |
|---|---:|---:|---:|---|
| BASELINE | 36.093 | 0.000 | 0.00 | cumple |
| R0 | 2015.517 | 100.000 | 5484.23 | refutada |
| R1 | 43.558 | 0.000 | 20.68 | cumple |

Variación de error se expresa en puntos porcentuales: una variación relativa desde 0% no está definida.

Execution ID: `d09a9f61af694ad0ada7297863948807`
Revisión: `51f758189dc7e156644627d43798a1a126da23be`

## BASELINE
Inicio UTC: 2026-11-17T05:59:36.522726+00:00
Fin UTC: 2026-11-17T06:01:36.367895+00:00
Trace de ejemplo: `7987fd0b9f264a2dbc346ad49c31f11d`
Inyección y reversión UTC: `{}`
Mayor retraso del generador: 27.747 ms. Reversión comprobada: True.

## R0
Inicio UTC: 2026-11-17T06:01:38.044865+00:00
Fin UTC: 2026-11-17T06:03:37.906161+00:00
Trace de ejemplo: `591aaf82e0ee496889f3575cd59566f9`
Inyección y reversión UTC: `{"injection_request_utc": "2026-11-17T06:02:08.041496+00:00", "injection_ack_utc": "2026-11-17T06:02:08.115816+00:00", "injection": {"requested": 6, "admitted": 6, "rejected": 0, "duration_seconds": 60, "protected": false}, "release": true, "release_verified_utc": "2026-11-17T06:03:08.203908+00:00"}`
Mayor retraso del generador: 27.225 ms. Reversión comprobada: True.

## R1
Inicio UTC: 2026-11-17T06:03:39.651350+00:00
Fin UTC: 2026-11-17T06:05:39.529873+00:00
Trace de ejemplo: `f857f4f155914742b53d13a1a0342d59`
Inyección y reversión UTC: `{"injection_request_utc": "2026-11-17T06:04:09.659902+00:00", "injection_ack_utc": "2026-11-17T06:04:09.734092+00:00", "injection": {"requested": 6, "admitted": 4, "rejected": 2, "duration_seconds": 60, "protected": true}, "release": true, "release_verified_utc": "2026-11-17T06:05:09.770645+00:00"}`
Mayor retraso del generador: 28.36 ms. Reversión comprobada: True.

