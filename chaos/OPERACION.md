# Operación del coordinador Inventario-U

Estado: implementación local; sin despliegue nuevo ni rondas cloud verificadas.
Inventario-U coordina consultas síncronas de inventario, deportista y artículo.
Su fallo asignado es latencia saliente. Los fallos de indisponibilidad y recursos
de los compañeros necesitan sus propios experimentos; este gate todavía no los ejecuta.

## Información que debe entregar el grupo

| Dato | Valor por confirmar |
| --- | --- |
| URL de Inventario-U experimental | Pendiente |
| URL y nube de deport-back | Pendiente |
| Ruta real de deportista y campo ID | `/deportistas/{id}` y `id`, sin verificar remotamente |
| URL y nube de api-fastify | Pendiente |
| Ruta real de artículo y campo ID | `/articulos/{id}` y `id`, sin verificar remotamente |
| SKU, almacén, deportista y artículo sintéticos válidos | Pendiente |
| Dependencia exacta a retrasar | Propuesta deport-back; confirmar |
| p95 máximo U y aceptación del éxito >=99% | Pendiente de línea base y acuerdo |
| Latencia 1500 ms, duración 60 s y perfil k6 | Propuesta versionada; confirmar |
| Ventana UTC autorizada | Pendiente |
| API completa desplegada en GKE y responsable de Chaos Mesh | Pendiente |

La ruta del coordinador es `GET /api/v2/integracion` con `sku_id`, `almacen_id`,
`deportista_id` y `articulo_id` en query params. No confundirla con la consulta
individual de inventario mediante QUERY. Enviar `X-Api-Key` y opcionalmente
`X-Trace-Id`; se genera uno si falta o es inválido. La respuesta contiene las tres
entidades y el trace ID. Las llamadas salientes usan el mismo trace y la clave
`TEAM_API_KEY` del entorno. No guardar claves en el repositorio ni colecciones.

## Preparar el host experimental

1. Acordar datos, objetivo, carga y ventana. Preparar una instancia aislada con
   el SHA exacto de esta rama. No modificar las APIs compartidas sin coordinar.
2. Configurar `DEPORTBACK_API_URL`, `FASTIFY_API_URL` y las rutas del entorno.
   Para R0 iniciar la API con `RESILIENCE_MODE=baseline`, `CHAOS_ROUND=R0`;
   para R1, `protected` y `R1`. Reiniciar entre rondas para limpiar circuitos.
   Exportar `APP_REVISION` con el SHA completo instalado.
3. En un host Linux dedicado instalar Docker, Python y uv; disponer de
   Prometheus con scrape del coordinador. No iniciar recursos facturables sin
   ventana, presupuesto y apagado independiente del portátil.
4. Crear solo un proxy Toxiproxy `chaos-*` dedicado a la dependencia elegida;
   control y Prometheus deben ser accesibles por loopback desde el runner.
   Configurar el coordinador experimental para pasar realmente por ese proxy.
   Las URLs HTTPS requieren conservar hostname, SNI y validación TLS: el diseño
   de esa ruta queda pendiente de las URLs reales. No desactivar certificados.
5. Crear un directorio persistente fuera del checkout para `CHAOS_LEASE_DB`,
   accesible únicamente al usuario del watchdog/runner. Copiar el ejemplo de
   entorno fuera de Git y completar valores; no se carga automáticamente.
6. Ejecutar `uv run --frozen --group chaos python -m chaos_lab.watchdog` como
   servicio supervisado separado del runner/job. Usar un checkout estable para
   el servicio, reinicio automático y la misma DB persistente y proxy. Sus
   variables son `CHAOS_TOXIPROXY_URL`, `CHAOS_PROXY_NAME`,
   `CHAOS_EXPECTED_UPSTREAM` y `CHAOS_LEASE_DB`. No iniciarlo desde el gate.
7. Antes de nube, reproducir `python -m scripts.verify_toxiproxy` localmente;
   después verificar en el host real la muerte del controlador y reversión
   automática. La prueba local no certifica este servicio en nube.

## Prevalidación y gate

`chaos/.env.example` enumera la configuración. `EXPECTED_APP_REVISION` debe ser
el SHA de 40 caracteres instalado; `CHAOS_RUN_ID` es un UUID hexadecimal nuevo
sin guiones. `CHAOS_WINDOW_ACK=GROUP_SYNTHETIC_ONLY` confirma el acuerdo, sin
sustituirlo. Al gate le deben quedar al menos cuatro minutos de ventana.

```bash
uv sync --frozen --group dev --group chaos
uv run --frozen --group chaos python -m scripts.check_group_contracts
uv run --frozen --group chaos python -m chaos_lab.gate
```

El primer comando de comprobación solo consulta: exige IDs correctos, eco de
trazas, las tres entidades, revisión instalada, ronda, modo y configuración de
dependencias coincidentes. URLs, rutas o secretos ausentes hacen fallar el gate.
No basta un 200 de health ni se infiere la nube o Kubernetes desde un hostname.

El gate inicia el perfil k6 fijo y espera estado estable medido. Ejecuta el
experimento declarativo con rollback obligatorio; exige muestras durante el
toxic real, éxito completo >=99%, p95 <=U y cero iteraciones descartadas.
Siempre intenta eliminar su propio toxic y comprobar recuperación del flujo.
Ante muerte abrupta del job actúa el watchdog independiente; validar ese caso
en la infraestructura elegida. Un fallo conserva salida no cero.

Los resultados privados quedan en `chaos/results/<run_id>/`. El informe JSON
resume contratos, perfil, mediciones, eventos reales de inyección, reversión y
recuperación. Revisar logs/journal antes de compartirlos; el workflow solo sube
`gate-report.json`, con comprobación de ausencia de claves.

## Run workflow en GitHub

El archivo `.github/workflows/chaos-gate.yml` está preparado, sin publicar ni
ejecutar en remoto. Para mostrar **Run workflow**, GitHub necesita registrar
`workflow_dispatch` en la rama predeterminada: publicar la rama sola no asegura
ese botón. Incorporar el workflow mediante revisión antes de la sustentación.

Configurar un runner `[self-hosted, Linux, inventario-chaos]` en el host dedicado
y un environment `chaos-group`. Crear `TEAM_API_KEY` como **secret**. Las demás
entradas de `.env.example` usadas por el workflow son **variables** del environment,
salvo ronda, ventana y run ID, que genera o recibe el workflow. La revisión
esperada es automáticamente el SHA seleccionado al ejecutar Actions.

En Actions seleccionar **Chaos gate del flujo de tres APIs → Run workflow**,
la rama instalada, R0/R1 y la ventana acordada. La API debe estar configurada con
esa misma ronda y SHA antes de pulsar. El workflow no despliega, enciende VMs ni
instala Chaos Mesh. Un runner sin preparar queda esperando; no es evidencia.

## Grafana y comparación

El tablero versionado `Inventario U - Caos R0 y R1` (`inventory-chaos`) se
provisiona junto al tablero canary. R0 aparece azul y R1 naranja. Muestra flujos,
éxito completo, p95 incluyendo errores y fallos por segundo. Publicarlo todavía
requiere desplegar los archivos y verificar scrape con datos reales.

Usar intervalo UTC de cada informe y crear una anotación de región con tag
`inventario-chaos`, desde `fault_injected` hasta `rollback_verified` en
`fault_events`. Confirmar contra el journal; la región corresponde a inyección
y eliminación observadas, no al inicio completo del job. Guardar capturas de
ambas rondas, logs del mismo trace y pruebas de recuperación.

```bash
uv run --frozen --group chaos python -m scripts.compare_chaos_rounds chaos/results/ID_R0/gate-report.json chaos/results/ID_R1/gate-report.json
```

La comparación rechaza cambios de perfil, fallo, umbral, revisión, URLs/rutas
o datos entre rondas. Calcula variación porcentual; con R0=0 informa `null`.
Una falla de configuración no cuenta como refutación. Si R1 no pasa el objetivo,
la comparación falla: timeout y circuit breaker no aseguran continuidad de
negocio ante una dependencia caída. Debe justificarse y medirse otra mejora.

Quedan para la entrega: tres nubes verificadas, GKE/Chaos Mesh, los otros dos
experimentos integrados, R0/R1 reales, dashboard y reversión en nube, análisis,
informe de máximo seis páginas y release SemVer con evidencia revisada.
