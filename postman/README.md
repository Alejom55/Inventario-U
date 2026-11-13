# Práctica de sustentación con Postman

Para la red universitaria, usar `http://157.137.207.154` como `base_url`,
sin `:8000`. Grafana está en
`http://157.137.207.154/grafana/d/inventory-canary/`.
OCI permite los puertos 80 y 8000 únicamente desde el CIDR autorizado.
Si cambia la red de salida, hay que actualizar ese CIDR antes de la práctica.

Postman prueba las peticiones de la API. GitHub Actions ejecuta la promoción
y el rollback; Grafana muestra las métricas. No se necesita controlar Docker
desde un endpoint público ni usar credenciales GitHub dentro de Postman.

## Importar

1. En Postman Desktop, abrir Import y seleccionar
   `Inventario-U-Canary.postman_collection.json`.
2. Importar `OCI-plantilla.postman_environment.json` y seleccionar ese entorno.
3. Completar localmente `team_api_key`, `grafana_user` y `grafana_password` con
   los accesos privados entregados. Mantener `allow_faults=false`.
4. También se entrega al propietario un entorno privado ya preparado fuera
   del repositorio. Ese archivo contiene credenciales y no se comparte con
   el profesor ni se adjunta al release. No compartir sus valores en Postman.

La colección pública y la plantilla no contienen secretos. El método `QUERY`
se importa directamente; si se crea una petición manual, escribir `QUERY`
como método y seleccionar Body, raw, JSON con cuerpo `{}`.

## Orden para mostrar al profesor

1. En `01 Comprobaciones iniciales`, enviar Stable v2. Mostrar las cabeceras
   `X-App-Version`, `X-App-Track` y `X-App-Revision`. La revisión queda guardada
   como `installed_revision` para identificar el despliegue.
2. Enviar Canary interno. Mostrar `X-Canary: true` y respuesta canary aunque
   el tráfico público esté en 0.
3. Enviar Inventario v2 y después Inventario v3. Mostrar `estado_stock` y
   `unidades_reponer`; las pruebas de v3 comparan los campos anteriores con
   una consulta real adicional a v2. Las peticiones no modifican inventario.
4. Enviar Reiniciar contadores una vez. Ejecutar SOLO la carpeta
   `02 Reparto publico y regresion` en Collection Runner, por ejemplo con
   100 iteraciones. La consola de Postman muestra conteos y porcentaje observado.
5. Iniciar `promote` desde el workflow Canary en OCI con la revisión instalada.
   Repetir las lecturas de Postman durante 10, 50 y 100 y observar Grafana.
6. Iniciar `regression` desde GitHub. Ese escenario genera carga e inyecta
   fallos automáticamente. Las lecturas públicas pueden devolver 500 canary;
   la prueba los cuenta y rechaza 500 stable. Al finalizar, las nuevas
   solicitudes públicas deben volver a stable.

Una muestra secuencial de Postman fluctúa y no reemplaza la puerta SLO. La
decisión de promoción utiliza la carga concurrente y las muestras mínimas
versionadas en `deploy/canary/policy.json`.

## Fallos manuales opcionales

La carpeta `03 Fallos manuales opcionales` permite practicar la inyección
por HTTP. Activar requiere `allow_faults=true`; el valor predeterminado hace
que Postman omita esa petición. Desactivar fallos queda disponible siempre.

Este endpoint por sí solo no inicia un controlador ni un rollback automático.
Para demostrar el aborto completo, usar el escenario `regression` de GitHub,
que coordina puerta de análisis, carga, fallo y recuperación. No ejecutar toda
la colección durante ese escenario: la petición Desactivar fallos podría
interrumpir la demostración. Usar las carpetas indicadas por separado.

## Grafana

La carpeta `04 Grafana por API` inicia sesión y prueba el dashboard de 18
paneles y la conexión de Prometheus. Postman conserva la cookie de sesión.
Para ver gráficas, abrir en el navegador la URL base seguida de
`/grafana/d/inventory-canary/` y usar el acceso privado.

## Verificación de la colección

Ejecutar `node postman/verify.mjs` valida JSON, sintaxis de scripts, protección
predeterminada de fallos y conteos por track. Las peticiones reales deben
comprobarse con la VM encendida y la IP del equipo autorizada en OCI.

Referencias oficiales:

- https://learning.postman.com/docs/use/send-requests/create-requests/request-basics
- https://learning.postman.com/v11/docs/tests-and-scripts/write-scripts/postman-sandbox-reference/pm-execution
