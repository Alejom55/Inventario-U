# Evidencias de ejecución real

Fecha: 14 de octubre de 2026, Bogotá. Los JSON registran UTC (15 de octubre).

| Evidencia | Resultado |
| --- | --- |
| [pipeline-success.png](pipeline-success.png) / [pipeline.json](pipeline.json) | GitHub Actions: validación y despliegue exitosos |
| [infraestructura.json](infraestructura.json) | 16 recursos administrados; información filtrada del estado |
| [oci-instancia-running.png](oci-instancia-running.png) | Instancia E5 ejecutándose durante la demo |
| [api-health.png](api-health.png) | Health público correcto |
| [api-swagger.png](api-swagger.png) | Swagger de la API desplegada |
| [api-real.json](api-real.json) | Health, autenticación, inventario PostgreSQL y Object Storage reales |
| [apagado.json](apagado.json) / [oci-instancia-stopped.png](oci-instancia-stopped.png) | Apagado posterior confirmado STOPPED |

[Ver ejecución en GitHub](https://github.com/Alejom55/Inventario-U/actions/runs/38666265881).
Revisión desplegada: `4e8d5d15ff5e6913f62592cc93ce94a19a7bf744`.
La release v2.1.0 conserva la versión HTTP de la API 2.0.0: es una entrega de
infraestructura y evidencia, sin cambiar el contrato de la API.

No se incluyen claves, valores de Vault, tfvars, planes ni estados Terraform.
Los registros corresponden a datos sintéticos. La VM está detenida; las capturas
son evidencia histórica de la ejecución, no una promesa de disponibilidad actual.
