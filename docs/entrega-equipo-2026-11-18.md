# Cifras y enlaces para el grupo

**DevOps, fallo c en AWS:** base **100 %** / R0 **0 %** / R1 **100 %**. Umbral R1 **>=99 %: cumple**. Patrones: **bulkhead y control de admisión** (6 tareas solicitadas; R0 admite 6, R1 admite 4 y rechaza 2). Perfil idéntico: 5 solicitudes/s, 120 s; ventana medida de fallo de 60 s, 300 muestras por ronda. Herramientas: Chaos Toolkit y generador HTTP asíncrono propio, no k6.

- [Run AWS aprobado 44209628616](https://github.com/Alejom55/Inventario-U/actions/runs/44209628616).
- [Resultados originales](https://github.com/Alejom55/Inventario-U/blob/feat/security-chaos-v4/docs/evidence/aws-cloud-results.json).
- [Muestras, journals, logs y hashes](https://github.com/Alejom55/Inventario-U/tree/feat/security-chaos-v4/docs/evidence/aws-fault-c).
- Execution ID: `dd2699928d6149b2ad7cc8d1dc9bc187`.

| Ronda | Inicio / fin UTC, 18 noviembre 2026 | Trace ID |
|---|---|---|
| Base | 00:40:40 / 00:42:40 | `23ff1ef5271641c5968003abff50364b` |
| R0 | 00:42:41 / 00:44:41 | `a8b01a06cd0e4974a3314f68c1fd0cab` |
| R1 | 00:44:42 / 00:46:43 | `fa6d21aee8db4f91aca3fb5ad64aea03` |

Inyección UTC R0: **00:43:11.646**, liberación verificada **00:44:11.991**. Inyección R1: **00:45:12.837**, liberación verificada **00:46:13.313**. Reversión verificada en las tres rondas. Son resultados de una API realmente desplegada en AWS, no ejecución local ni demostración de toda la cadena.

**E1 oficial:** MTTD R0 **pendiente** / R1 **pendiente**; MTTC R0 **pendiente** / R1 **pendiente**; cobertura R0 **pendiente** / R1 **pendiente**; falsos positivos R1 **pendiente**. [Implementación, detección positiva/negativa y tablero](https://github.com/Alejom55/Inventario-U/tree/feat/security-chaos-v4/security). Falta recibir y aceptar las reglas exactas del grupo antes de R0. Objetivo declarado: MTTD <=30 s; contención sostenida <=5 s como guardarraíl. No son resultados medidos todavía.

**Servicio restaurado y verificado:** API base **https://3.147.57.31.sslip.io/api/v2**; Prometheus **https://3.147.57.31.sslip.io/prometheus**. Misma API key y Bearer de métricas. GET SKU **200**, inventario GET/QUERY **200**, `sku_id=1`, `almacen_id=1`, stock sintético **8**. Nueva VM `i-094c00455c9ac62ba`, revisión `c2ee1dc85710563768a844a671bc61b2d1f69ead`. **Apagado manual: sin fecha automática.** El usuario autorizó continuar usando créditos Free incluso por encima del límite anterior de USD 1, hasta indicar apagar. [Verificación actual](https://github.com/Alejom55/Inventario-U/blob/feat/security-chaos-v4/docs/evidence/aws-manual-shutdown.json). [Disponibilidad actual](https://github.com/Alejom55/Inventario-U/blob/feat/security-chaos-v4/docs/evidence/aws-demo-availability.json) y [protecciones AWS](https://github.com/Alejom55/Inventario-U/blob/feat/security-chaos-v4/docs/evidence/aws-demo-control-verification.json).

La IP anterior terminó automáticamente a las 21:29:50 COL. **Actualizar la URL en deport-back y Fasty antes de usar la demo.** No se ha repetido ningún fallo en la VM restaurada; los resultados superiores mantienen la procedencia de la corrida anterior. Grafana Cloud común requiere iniciar sesión para conectar la fuente; sus capturas siguen pendientes.

**Plazos comunicados por el grupo:** R1 antes del **18 de noviembre, 14:00 COL = 19:00 UTC**; cierre del informe **18:00 COL = 23:00 UTC**. Estos plazos no sustituyen la ventana específica de las reglas firmadas.
