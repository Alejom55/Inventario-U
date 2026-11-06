# Sustentación individual del despliegue canary

## Explicación inicial

Inventario-U administra SKU, almacenes y movimientos en PostgreSQL. La versión
canary añade a la consulta de inventario el estado del stock y las unidades por
reponer. La versión estable conserva su contrato. Las dos versiones corren en
OCI Compute y comparten datos sin una migración destructiva. Nginx limita qué
porcentaje del tráfico público recibe la nueva versión. Prometheus y Grafana
permiten decidir con métricas cuándo promover o regresar a stable.

## Preparación de la demostración

1. Confirmar que la cuenta permite usar la VM y que está encendida. Si la prueba
   gratuita terminó, revisar coste y capacidad antes de reactivarla.
2. Verificar que `install` terminó con smoke checks aprobados y canary público en 0.
3. Abrir Grafana en `/grafana/d/inventory-canary/`, iniciar sesión y seleccionar
   últimos quince minutos con actualización cada cinco segundos.
4. Tener disponibles el repositorio, `policy.json`, pipeline y el archivo de
   decisiones. Mostrar la revisión y el identificador SHA256 del artefacto.
5. Usar la clave de API por variable de entorno. No mostrarla en pantalla ni
   pegarla en el historial del repositorio.

Los siguientes ejemplos usan PowerShell. Definir `$base` con la URL autorizada
y `$env:TEAM_API_KEY` mediante el mecanismo privado habitual.

```powershell
$headers = @{ 'X-Api-Key' = $env:TEAM_API_KEY }
$preview = @{ 'X-Api-Key' = $env:TEAM_API_KEY; 'X-Canary' = 'true' }
Invoke-WebRequest "$base/api/live/health" -Headers $headers
Invoke-WebRequest "$base/api/live/health" -Headers $preview
Invoke-RestMethod "$base/api/v2/inventario/query" -Method QUERY -Headers $headers -ContentType 'application/json' -Body '{}'
Invoke-RestMethod "$base/api/v3/inventario/query" -Method QUERY -Headers $headers -ContentType 'application/json' -Body '{}'
```

En Windows PowerShell antiguo, usar PowerShell 7 o `curl.exe -X QUERY` para el
método extendido. Explicar que las rutas fijas no forman parte de la muestra
pública de porcentajes.

## Escenario de promoción exitosa

Ejecutar `promote` en el workflow `Canary en OCI` usando la misma revisión que
se instaló. Mostrar primero 0 público y la solicitud interna con track canary.
Durante 10 y 50 mostrar el reparto observado en los eventos `analysis`, que
cuentan únicamente peticiones públicas. Enseñar al lado el volumen, 5xx, 4xx,
p50, p95, p99, CPU, memoria y consultas completadas de cada track en Grafana.

Antes de avanzar, explicar los 1000 pedidos por track en la ventana, el horneado
y los límites. Al terminar, mostrar `promoted` con 100 y la respuesta pública
canary. La ruta fija v2 permite comprobar que stable sigue disponible como
baseline. La promoción cambia enrutamiento, no reconstruye la imagen.

## Escenario de regresión y rollback

Ejecutar `regression`. El controlador reinicia en 0 y compara ambas versiones.
En 10 activa 50 por ciento de errores únicamente en lecturas canary. Mostrar el
evento `fault_enabled`, el aumento de 5xx en Grafana y la decisión `abort` con
los valores que violaron la política. El proxy vuelve a 0 y el controlador
comprueba 30 consultas públicas consecutivas atendidas por stable.

Mostrar `rollback_verified`, recuperar el mismo inventario y comprobar que el
stock permanece igual. El interruptor se desactiva al terminar. El retorno a
stable no restaura un dump ni borra movimientos válidos. El aborto se ordena al
detectar la regresión; la detección usa consultas cada diez segundos y no es
instantánea desde la primera petición defectuosa.

## Preguntas y respuestas

**¿Qué diferencia canary de rolling update?** Rolling reemplaza instancias por
lotes. Canary mantiene una versión candidata con exposición limitada y una
decisión de promoción basada en métricas. Una actualización rolling por sí sola
no exige comparar contra baseline ni controlar un porcentaje público preciso.

**¿Qué diferencia tiene frente a blue green?** Blue green mantiene dos entornos
y normalmente cambia el tráfico de uno a otro. Canary añade exposición gradual
y análisis antes de completar el cambio. Dos contenedores por sí solos no
demuestran una estrategia canary.

**¿Por qué no es una prueba A B?** A B compara variantes para medir resultados
de producto, generalmente con grupos persistentes. Aquí se evalúa seguridad
operativa de una versión antes de promoverla.

**¿Una feature flag sustituye canary?** Una flag controla una función dentro de
una aplicación. Puede complementar la exposición gradual, pero no identifica
por sí sola qué artefacto recibe tráfico ni proporciona rollback de despliegue.

**¿Qué es shadow?** Duplica solicitudes hacia una candidata sin usar su respuesta
para el usuario. Debe aislar efectos de escritura. Aquí canary atiende solicitudes
reales y devuelve su respuesta.

**¿Cuál es el radio de impacto?** En 10, aproximadamente ese porcentaje de las
peticiones públicas elegibles llega a canary. No significa exactamente 10 por
ciento de usuarios ni limita una regresión que afecte una dependencia compartida.

**¿Cómo se reparte el tráfico?** El proxy calcula el track sobre un identificador
aleatorio por petición. Las rutas fijas y sondas autenticadas se cuentan aparte
en la evidencia pública. Hay variación muestral en etapas intermedias.

**¿Por qué no hay sticky sessions?** La API no conserva sesión local. Las
peticiones pueden cambiar de track sin perder contexto. Si hubiera sesiones
locales, se necesitaría un almacén compartido o una estrategia de afinidad y
se volvería a evaluar cómo medir porcentajes por petición y por usuario.

**¿Qué son SLI y SLO?** Un SLI mide comportamiento observable, como proporción
5xx o p95. Un SLO establece el objetivo y la ventana. Aquí la política fija
umbrales antes del despliegue. Un SLA sería un compromiso contractual distinto.

**¿Por qué medir también 4xx?** Una ruptura de contrato puede aumentar 4xx sin
generar 500. Se miden aparte para distinguir errores de cliente y regresiones.

**¿Por qué p95 y p99 además del promedio?** El promedio puede ocultar una cola
de peticiones lentas. Los percentiles resumen esa cola. Los histogramas estiman
percentiles según buckets; no son mediciones exactas de cada posición ordenada.

**¿Cómo se compara justamente con baseline?** Se usa el mismo método QUERY,
cuerpo, autenticación, datos, límites de recursos y ventana. Las sondas compensan
el reparto público para equilibrar carga esperada entre versiones. Al compartir
VM y base existe interferencia; la demo no prueba aislamiento entre hosts.

**¿Mil solicitudes garantizan ausencia de defectos?** No. Son una barrera mínima
de esta demo. Con cero errores, la regla aproximada de tres ofrece un límite
superior cercano a 0,3 por ciento al 95 por ciento, bajo supuestos de independencia.
Tráfico real puede estar correlacionado y necesitar muestras mayores, mezcla de
operaciones y más tiempo de observación.

**¿Qué ocurre si faltan métricas?** Nunca se promueve. La etapa pausa y, si no
obtiene evidencia suficiente antes del plazo, aborta a 0. Un baseline degradado
tampoco sirve para aprobar o atribuir automáticamente el problema a canary.

**¿Qué métrica representa negocio?** Consultas de inventario completadas. La
puerta exige que representen al menos 99 por ciento de la muestra. Una consulta
que responde 200 pero incumple semántica requiere además pruebas de contrato;
por eso los smoke checks comparan stock y campos entre v2 y v3.

**¿Dónde se aplica Expand Contract?** La expansión añade campos de respuesta
y mantiene tablas y lectores anteriores. No hay DDL canary. La contracción se
aplaza; retirar campos o tablas mientras v2 funciona impediría un rollback seguro.

**¿Qué se conserva al hacer rollback?** Datos aceptados, base compartida, objetos
y versión candidata para diagnóstico. Solo se retira su tráfico público. Las
peticiones en curso pueden finalizar; volver a 0 no revierte efectos ya guardados.

**¿Qué hace inmutable el despliegue?** La instalación resuelve el ID de contenido
SHA256 de una imagen. Los pasos de promoción reutilizan ese ID. Un tag como
`latest` puede cambiar y no sería una identidad adecuada para esa transición.

**¿Qué antipatrones evita?** Promover sin muestra, cambiar umbrales después de
ver un fallo, comparar distintas cargas, usar migraciones destructivas, confundir
health 200 con semántica correcta y presentar pruebas locales como evidencia OCI.

## Evidencias que conservar

Capturas de OCI y del pipeline, respuestas con cabeceras, comparación de campos
de stock, dashboard durante promoción y fallos, decisiones con muestras y
porcentajes, rollback verificado y release desde el tag final. Registrar fecha,
revisión y tipo de entorno. Nunca adjuntar claves ni un archivo de entorno.
