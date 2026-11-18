# Capturas de resultados y paneles

Las rondas reales de DevOps provienen del run AWS 44209628616 y de la instancia anterior. Los paneles de telemetría actual corresponden a la VM restaurada. El tablero identifica ambas fuentes.

Las pruebas E1 de software y reglas positivas/negativas no son rondas oficiales de Ciber. Las rondas oficiales y sus capturas de alerta siguen pendientes de reglas de compromiso aceptadas.

## Índice

- 01: conexión exitosa de Grafana Cloud a Prometheus autenticado.
- 02: comparación archivada BASELINE/R0/R1 y alcance de la VM actual.
- 03 y 04: telemetría real actual (tráfico, latencia, CPU, memoria y disponibilidad).
- 05 y 06: ejecución real AWS aprobada y cifras del log original.
- 07: validación de software E1; incluye casos de detección positiva/negativa y aviso de que no es evidencia cloud.

Tablero: https://niftyivy3144.grafana.net/d/inventario-aws-evidence

Se generaron 20 consultas de lectura, todas HTTP 200, para comprobar visualización. No se inyectaron fallos ni se ejecutó E1 oficial durante estas capturas. Las capturas muestran la hora local del navegador; el tablero identifica las ventanas históricas en UTC.

- 08: validación completa del repositorio con PostgreSQL, Terraform e imagen Docker.
- 09: resumen de pytest en CI: **339 pruebas aprobadas**, 19 avisos de obsolescencia, **94,27 % de cobertura** (umbral 85 %). Fuente: run 44232493710.

Las imágenes son capturas reales del navegador, recortadas para excluir la barra lateral de chats. No se alteraron cifras ni se añadieron gráficos artificiales.
