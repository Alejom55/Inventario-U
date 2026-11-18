# E1 medido en AWS: ficha para el informe

Responsable: Alejandro Marín. VM: `i-094c00455c9ac62ba`, AWS Ohio.
Laboratorio aislado: https://e1.3.151.219.131.sslip.io.
Autorización individual explícita del propietario; no representa firmas grupales.

Hipótesis: con 10 lecturas legítimas y 10 intentos de creación usando una identidad
de lectura, máximo 2 peticiones/s y observación de 30 s, R1 detecta el abuso con
**MTTD <=30 s**. Único objetivo. Guardarraíles: rechazo sostenido, MTTC <=5 s y
reversión. R0 usa API key sin alcance; R1 exige JWT Ed25519 con identidad, alcance
y vencimiento, más credencial señuelo rechazada con alerta.

| Medición | R0 | R1 |
|---|---|---|
| MTTD | No detectado en 30,828 s | 5,484 s |
| MTTC sostenido | No contenido | 0,500 s |
| Cobertura | 0/1 técnica | 1/1 técnica |
| Lecturas legítimas rechazadas | 0/10 (0 %) | 0/10 (0 %) |
| Escrituras indebidas aceptadas | 10/10 (100 %) | 0/10 (0 %) |
| Reversión | Verificada | Verificada |
| Inyección UTC, 18/11/2026 | 05:39:31.301 | 05:41:11.219 |
| Objetivo MTTD <=30 s | No cumple | Cumple |

R0: `f5c0fde699874f6b90f916d2f0b3d751`, 05:39:24-05:40:17 UTC.
R1: `8f1e8c3e4ecb47b7ab76d333d150e75a`, 05:41:04-05:41:44 UTC.

R0 censurado no equivale a cero. MTTD es el límite superior hasta observar ALERTS
en Prometheus. MTTC incluye cadencia del cliente y exige rechazo sostenido.
La cobertura se refiere a una técnica conceptual T1078; los falsos positivos del
ejecutor cuentan rechazos de lecturas legítimas y no son el FPR del detector E3-A.
Diez muestras no garantizan comportamiento de producción.

Parada: `uv run python -m deploy.security.aws_e1 stop`, desde el equipo operador.
STOP es cooperativo; finally elimina solo sus SKU y verifica GET 404 y salud 200.
No apaga la VM ni la API grupal. Repetición: `state`, `authorize --minutes 60`,
`R0` y `R1` sobre el mismo módulo. No retirar STOP sin revisar su causa.

- [Reportes, logs y hashes originales](../docs/evidence/ciber-e1-aws/).
- [Capturas reales de Grafana](../docs/evidence/ciber-e1-grafana/).
- [Tablero Ciber E1 AWS](https://niftyivy3144.grafana.net/d/inventario-security-e1-aws).
- [Pipeline de verificación](https://github.com/Alejom55/Inventario-U/actions/runs/44247381296): aprobado; valida mediciones ya obtenidas, no inyecta las rondas.
- [Regla y casos positivo/negativo](detection/).
- [PDF de resultados medidos](../output/pdf/Inventario-U-Ciber-E1-AWS-resultados-reales.pdf).

La API compartida sigue en https://3.151.219.131.sslip.io/api/v2, con su clave
original y apagado manual. Se verificó 200 durante y después de ambas rondas.
La recreación entre rondas afecta solo e1-api y explica el descenso puntual de up.
Las alertas de contador permanecen activas hasta recrear ese proceso.
