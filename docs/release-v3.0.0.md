# Canary Deployment en OCI

Inventario-U incorpora una estrategia canary con stable v2 y canary v3,
identificación por respuesta y una ampliación compatible de la consulta de stock.

- Etapas públicas 0, 10, 50 y 100 por ciento con horneado, muestras mínimas y
  validación del reparto observado.
- Comparación de tráfico, 4xx, 5xx, p50, p95, p99, CPU, memoria y consultas de
  inventario en Prometheus y Grafana.
- Puerta SLO versionada con decisiones de promoción, pausa y aborto; inyección
  autenticada de fallos solo canary y rollback verificado mediante consultas stable.
- Instalación en OCI Run Command con backup previo y artefacto SHA256 inmutable.
- Ensayo local aislado, pruebas de contrato y guion de sustentación individual.

La versión v3 añade `estado_stock` y `unidades_reponer`. La API v2 mantiene los
campos anteriores. No se incorpora una migración destructiva. La contracción de
esquema queda aplazada hasta retirar v2 y cerrar la ventana de rollback.

La guía `docs/canary-operacion.md` documenta instalación, permisos, credenciales
privadas, límites de la demo y ubicación de evidencias.

## Validación real en OCI

La imagen final completó las etapas 0, 10, 50 y 100 por ciento. El reparto público
observado fue 0, 9,68, 51,17 y 100 por ciento, con horneado completo y más de
1700 peticiones por track en cada ventana aprobada. El p95 canary permaneció
por debajo de 294 ms frente al límite de 500 ms.

Al inyectar 50 por ciento de fallos, la ventana detectó 7,62 por ciento de 5xx
canary y 0 por ciento stable. El sistema abortó, volvió a 0 público canary y
verificó 30 consultas stable. El hash de inventario permaneció idéntico.

Grafana aprobó login real, API autenticada del dashboard y conexión con
Prometheus; tiene 18 paneles. GitHub Actions aprobó 176 pruebas, cobertura de
93,33 por ciento, cinco pruebas Terraform, Bash y ensayo Docker. El workflow
manual Canary ejecutó rollback real sobre la VM.

E5 quedó apagada mediante SOFTSTOP después de 56,10 minutos, dentro de la
ventana autorizada. Para repetir la sustentación, encender la VM y usar la
revisión instalada indicada en `docs/evidencias-canary/oci-summary.json`.
Los accesos privados se entregan fuera del repositorio y del ZIP.

Evidencias completas: [docs/evidencias-canary](https://github.com/Alejom55/Inventario-U/tree/v3.0.0/docs/evidencias-canary).
