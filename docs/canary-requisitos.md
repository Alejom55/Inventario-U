# Criterios de aceptación del despliegue canary

La entrega reutiliza Inventario-U en OCI Compute. La versión estable v2 y la
versión canary v3 comparten PostgreSQL y Object Storage. El proxy distribuye
peticiones nuevas; no se usa afinidad de sesión porque la API es stateless.

| Requisito | Implementación y evidencia esperada |
| --- | --- |
| Versiones simultáneas | Contenedores separados y cabeceras de versión, track y revisión |
| Cambio funcional v3 | Estado de stock y unidades por reponer en la consulta de inventario |
| Compatibilidad | Ampliación de respuesta sin DDL destructivo ni cambio de claves de objetos |
| Tráfico progresivo | 0, 10, 50 y 100 por ciento con tiempos y muestras mínimas |
| Acceso interno en 0 | Cabecera de selección y clave de API válida |
| Artefacto inmutable | Construcción única y ejecución por identificador SHA256 de imagen |
| Señales doradas | Peticiones, 4xx, 5xx, p50, p95, p99, CPU y memoria por track |
| Métrica de negocio | Consultas de inventario completadas por track |
| Análisis | Umbrales versionados, carga concurrente y comparación con baseline |
| Fallos controlados | Error o demora exclusivamente en canary con autorización |
| Rollback | Puerta automática que vuelve a 0 y verifica stable |
| Tablero | Grafana con comparación simultánea de ambos tracks |
| Sustentación | Guion de promoción, aborto y preguntas conceptuales |
| Trazabilidad | Commits GitMoji, SemVer y release desde un tag |

Las comprobaciones locales, la ejecución del pipeline y las pruebas reales en
OCI son evidencias distintas. Registrar resultados reales sin sustituirlos por
las evidencias históricas de Terraform.
