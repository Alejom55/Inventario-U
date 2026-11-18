# Capturas reales de Grafana: E1 AWS

Tablero: https://niftyivy3144.grafana.net/d/inventario-security-e1-aws

Intervalo mostrado: 18/11/2026, 05:38:30-05:43:00 UTC.
VM: i-094c00455c9ac62ba. Fuente: Inventario E1 AWS, UID fg4n7aqm8d98ga.

- `01-e1-resumen-y-tiempos.png`: método, cifras medidas, IDs y tiempos.
- `02-e1-mttd-mttc-cobertura-fpr.png`: MTTD, MTTC, cobertura y rechazos de lecturas legítimas.
- `03-e1-alertas-senuelo-y-telemetria.png`: alertas nativas, decisiones, señuelo y recolección.

Capturas del navegador en píxeles nativos, recortadas para retirar la interfaz
externa o filas ajenas a los paneles seleccionados. Sin ampliación, recreación
de gráficas ni modificación de valores. No contienen credenciales.

R0: f5c0fde699874f6b90f916d2f0b3d751. R1: 8f1e8c3e4ecb47b7ab76d333d150e75a.
Reportes, logs y hashes: `docs/evidence/ciber-e1-aws/`.
Ejecución individual autorizada por el propietario; no representa firmas grupales.

R0 sin tiempos observados no equivale a 0 s. La cobertura se refiere a una
técnica y los falsos positivos del ejecutor a 10 lecturas legítimas. Las alertas
usan un contador y permanecen activas hasta recrear la API aislada, aunque la
carga ya haya terminado. El descenso puntual de `up` entre las rondas corresponde
al cambio controlado de política mediante recreación de `e1-api`; la API grupal
no se reinició y su respuesta 200 se verificó durante y después de las pruebas.
