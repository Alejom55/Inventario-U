# Evidencias de Canary Deployment en OCI

La solución se probó en Docker Desktop y en la VM real de OCI el 5 de noviembre
de 2026, hora de Colombia. Los eventos conservan fecha UTC. El resumen de nube
registra revisión instalada, imagen SHA256, promoción, aborto, integridad del
inventario, resultados de GitHub Actions y apagado dentro del tiempo autorizado.

## Validación en OCI

`oci-summary.json` presenta los resultados finales. `oci-promote.json` y
`oci-regression.json` conservan decisiones y métricas completas. Para revisar
el último ensayo, tomar el último evento `start` del escenario correspondiente;
los eventos anteriores permanecen para conservar trazabilidad.

La promoción recorre 0, 10, 50 y 100 por ciento con tiempos completos,
al menos 1000 peticiones por track en cada ventana aprobada y comparación de
errores, percentiles, CPU, memoria y consultas de inventario. Todas las etapas
de un ensayo conservan la misma imagen de aplicación por ID SHA256.

La regresión configura 50 por ciento de errores únicamente en canary durante
la etapa 10. La puerta detecta la violación, vuelve a 0 público canary y verifica
30 consultas stable. La ventana de 60 segundos incluye peticiones saludables
anteriores; por eso la primera alerta no muestra necesariamente 50 por ciento.
El inventario conserva el mismo hash.

`oci-install.json` documenta la instalación inicial y `oci-final-install.json`
la revisión final. `oci-api-contract.json` comprueba versiones de respuesta,
ampliación de stock en v3, login real de Grafana, dashboard autenticado y
conexión con Prometheus. El tablero tiene 18 paneles. Grafana se validó por
HTTP y API autenticada; no incluye revisión visual autenticada.

`github-validation.json` contiene los enlaces a CI y al workflow manual Canary.
La validación de código aprobó 176 pruebas con cobertura de aplicación de
93,33 por ciento, cinco pruebas Terraform, sintaxis Bash y ensayo HTTP Docker.
El workflow manual también ejecutó rollback real en la VM usando Run Command.

Las credenciales no forman parte de esta carpeta, del ZIP ni del release.
El acceso privado del operador se recuperó por HTTPS desde el bucket privado
y se retiró esa copia después de guardarla fuera del repositorio.

## Ensayo local previo

`local-summary.json` y los JSONL locales corresponden al ensayo Docker anterior:
173 pruebas aprobadas y promoción y rollback comprobados. Las revisiones locales
preceden a la normalización de dos mensajes GitMoji; el resumen contiene la
correspondencia y el hash de aplicación comprobado.

Las evidencias históricas de `docs/evidencias/` pertenecen a Terraform v2.
El estado final de la VM y el tiempo de uso están en el resumen de nube.
