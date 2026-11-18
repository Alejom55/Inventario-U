# Ficha E1 para incorporar al informe grupal

**Estado: pendiente de ejecución cloud. No entregar como informe de resultados.**

Responsable: Alejandro Marín. Servicio: Inventario-U. Experimento: reutilización de una credencial de lectura para crear SKU sintéticos (identidad de máquinas). Objetivo único: MTTD <= 30 s. Método idéntico por ronda: 10 lecturas legítimas y 10 intentos adversos, máximo 2 peticiones/s, observación primaria de 30 s. Guardarraíl: rechazo sostenido y MTTC <= 5 s.

R0: API key sin alcance por operación. R1: JWT Ed25519 de vida corta con emisor, audiencia, sujeto y alcance verificados; credencial señuelo con alerta y revisión humana. Correspondencias propuestas: NIST AC-3/AC-6/IA-5/IA-9/AU-12/SI-4, ISO A.5.16/A.5.17/A.8.3/A.8.5/A.8.15/A.8.16, ATT&CK T1078; D3FEND CTS/AZET/DST.

| Medición real | R0 | R1 |
|---|---|---|
| Execution ID / revisión AWS | PENDIENTE | PENDIENTE |
| Inyección UTC / trace_id de ejemplo | PENDIENTE | PENDIENTE |
| MTTD, límite superior observado | PENDIENTE | PENDIENTE |
| MTTC sostenido | PENDIENTE | PENDIENTE |
| Cobertura de técnica / FPR | PENDIENTE | PENDIENTE |
| Intentos adversos aceptados | PENDIENTE | PENDIENTE |
| Señuelo y alerta nativa | No aplica | PENDIENTE |
| Reversión y prueba GET 404 | PENDIENTE | PENDIENTE |

Usar «no detectado dentro de 30 s» cuando MTTD esté censurado; no reemplazarlo por 0 ni calcular una mejora porcentual contra `null`. La cobertura se calcula sobre una técnica; el FPR sobre las diez lecturas legítimas. RPO/RTO corresponden a E4. Los resultados previos de agotamiento de concurrencia son DevOps y no rellenan esta tabla.

Conclusión contrastada por persona: PENDIENTE. Comparación con análisis de IA: PENDIENTE. Captura de tablero y referencias a archivos originales: PENDIENTE. Este bloque busca ocupar una página dentro del informe grupal de máximo diez páginas, una vez reemplazados todos los pendientes por evidencia real.

## Texto para pedir al grupo

«La API grupal tiene Elastic IP: https://3.151.219.131.sslip.io/api/v2. Actualicen INVENTARIO_U_URL; la API key no cambió. Prometheus para Grafana: https://3.151.219.131.sslip.io/prometheus, con el mismo Bearer privado. Grafana Cloud ya validó la conexión. La VM queda encendida hasta mi orden de apagado. E1 está implementado y probado offline; todavía NO hay R0/R1 oficiales ni cifras MTTD/MTTC. Preparé el borrador de las reglas grupales con parada y reversión. La ventana propuesta del 18/11, 15:00-16:00 UTC (10:00-11:00 COL), sigue pendiente de confirmar sin solapamientos y de las tres firmas. Los resultados anteriores son DevOps, fallo c; no deben rellenar E1».
