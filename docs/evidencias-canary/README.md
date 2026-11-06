# Evidencias locales de Canary Deployment

El ensayo se ejecutó en Docker Desktop el 5 de noviembre de 2026, hora de
Colombia. Los eventos conservan fecha UTC. Esta carpeta demuestra ejecución
local; la instalación y demostración en OCI siguen pendientes.

`local-summary.json` contiene el resultado, identidades de imagen, hash del
árbol de aplicación y los porcentajes observados. Los JSONL conservan las
decisiones completas de promoción y de regresión, sin claves ni contraseñas.

La promoción recorrió 0, 10, 50 y 100 por ciento con los tiempos completos de
la política versionada y al menos 1000 solicitudes por track en cada ventana
aprobada. El dashboard provisionado tiene 18 paneles; se comprobó su API,
la conexión con Prometheus y que las 18 consultas retornan datos. No se hizo
una revisión visual autenticada del dashboard en navegador.

En la regresión, la puerta detectó 8,15 por ciento de 5xx canary y 0 por ciento
stable, regresó a 0 público canary y verificó 30 consultas stable. Desde la
decisión hasta completar la verificación transcurrieron 4,43 segundos. El
inventario consultado antes y después fue idéntico. La inyección se desactivó
al terminar y los smoke checks volvieron a aprobarse.

Cada escenario registra su propia imagen; todas las etapas de un escenario
reutilizan el mismo ID inmutable. Las dos imágenes ensayadas contienen el mismo
árbol `app`; se construyeron antes y después del ajuste de versión del paquete.

Las revisiones registradas en los JSONL preceden a la normalización de dos
mensajes GitMoji del historial local. Esa normalización no cambió archivos.
El resumen incluye la correspondencia de revisiones y el hash de aplicación
comprobado contra la rama entregada.

Validación adicional: 173 pruebas aprobadas, cobertura de aplicación de 93,33
por ciento, sintaxis Bash aprobada, YAML de workflows y Compose válido, y
`promtool check config` aprobado. Los scripts de host se comprobaron con la
sintaxis Python 3.9; falta ejecutarlos en el intérprete real de Oracle Linux.
Los chequeos Terraform y el workflow remoto se comprobarán en GitHub Actions
después de publicar la rama.

La lectura actual de OCI confirmó `inventario-u-s3` detenida, forma E5 y Run
Command habilitado. No se reactivó la instancia ni se aplicó Terraform.
