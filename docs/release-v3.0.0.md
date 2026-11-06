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
privadas, límites de la demo y ubicación de evidencias. La publicación del tag
y de estas notas no sustituye la validación en una VM real de OCI.
