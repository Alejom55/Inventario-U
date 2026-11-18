# Inventario-U: AWS con plan gratuito

API: https://3.147.57.31.sslip.io
Prometheus para Grafana Cloud: https://3.147.57.31.sslip.io/prometheus
Instancia actual: i-094c00455c9ac62ba; aplicación: c2ee1dc85710563768a844a671bc61b2d1f69ead.
El plan FREE se verificó antes de crear recursos. No se habilitó un plan de pago.
Solo créditos gratuitos; el cálculo reservado de la práctica es USD 0,775, dentro de USD 1 en créditos.
Terminación automática: 2026-11-18T23:00:00+00:00 (18 de noviembre, 18:00 COL). Se elimina el disco sintético.
La URL depende de esta IP y no se conserva para otro lanzamiento.

## Postman

GET https://3.147.57.31.sslip.io/api/v2/skus
Headers: X-Api-Key: {{inventario_api_key}} y X-Trace-Id: equipo-{{$guid}}.
Esperado: 200 con lista de SKU. Es un endpoint terminal, sin llamadas a los compañeros.
GET https://3.147.57.31.sslip.io/api/v2/inventario?sku_id=1&almacen_id=1
Devuelve resultados[]. El método QUERY /api/v2/inventario/query sigue disponible.
Conserva CRUD de SKU, almacenes y movimientos. Usar exclusivamente datos sintéticos.

## Grafana Cloud

Crear datasource Prometheus con la URL anterior, método POST y header seguro
Authorization: Bearer <token privado de métricas>. Importar docs/aws-dashboard.json.
Las claves se entregan por privado; no ponerlas en paneles ni en el grupo.
Cero tráfico sin peticiones es normal. Una petición aislada apenas cambia una tasa.
Los indicadores del cliente se publican al terminar la ronda, contando timeouts.
Estos gráficos comparan BASELINE/R0/R1 de una API; no son dos versiones Canary.

## Resultados reales históricos

La corrida 44209628616 corresponde a la instancia anterior i-03dee81b7d92a60c8.
No se atribuye a la VM repuesta. Las muestras, journals y logs originales están
en `docs/evidence/aws-fault-c/`. La disponibilidad de la VM actual se verificó
por separado en `docs/evidence/aws-demo-availability.json`; su comprobación de
protecciones nativas está en `docs/evidence/aws-demo-control-verification.json`.

Perfil: 5 peticiones/s, 120 s; agotamiento de concurrencia desde t=30 durante 60 s.
Único objetivo: éxito del cliente >=99%. Guardarraíl separado: p95 <500 ms.
R0 ocupa los seis trabajadores compartidos. R1 usa bulkhead y admite cuatro tareas
de fondo, rechazando dos sin cola. Reversión verificada en las tres rondas.
Generador: GitHub-hosted Ubuntu. Comparar únicamente rondas del mismo origen.
Execution ID: dd2699928d6149b2ad7cc8d1dc9bc187.

| Ronda | Éxito % | p95 ms | Variación p95 % |
|---|---:|---:|---:|
| BASELINE | 100.000 | 82.779 | 0.00 |
| R0 | 0.000 | 2128.845 | 2471.72 |
| R1 | 100.000 | 82.624 | -0.19 |

Para otra ejecución coordinada: Actions > Validacion local de caos > Run workflow > feat/security-chaos-v4 > Run workflow. No ejecutar mientras el grupo usa la demo: R0 degrada el servicio. La corrida histórica se inició desde feat/aws-chaos. Coordinar R0 con el grupo antes de ejecutarla. Solo funciona durante la ventana autorizada.

Para las IA: consumir /api/v2/skus y las otras rutas propietarias; nunca llamar a /integracion desde una dependencia. Enviar X-Api-Key desde secretos, propagar X-Trace-Id, establecer timeouts y tratar respuestas no 2xx como errores.

Esta evidencia corresponde a una API en AWS. No acredita la integración de las tres APIs ni Chaos Mesh/GKE. El Grafana Cloud común requiere que su responsable agregue la fuente y el tablero.

Ejecución: https://github.com/Alejom55/Inventario-U/actions/runs/44209628616
