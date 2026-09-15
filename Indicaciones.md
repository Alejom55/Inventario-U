Estoy trabajando en el repositorio Inventario-U para una entrega de DevOps multicloud. Necesito que revises completamente el proyecto actual antes de modificar archivos y que implementes la versión 2 de la API, reutilizando toda la lógica existente y sin romper la API actual.

Contexto del proyecto

Mi API es una API de inventario y actualmente maneja entidades como:

SKU
Almacén
Movimiento
consultas relacionadas con inventario

La entrega exige reutilizar la API de la primera entrega y crear una nueva versión utilizando el prefijo:

/api/v2

No quiero reescribir la lógica de negocio ni duplicar innecesariamente código. La V2 debe reutilizar servicios, repositorios, modelos, esquemas y lógica existente siempre que sea posible.

También trabajo con otros dos integrantes cuyos repositorios son:

Integrante B:
https://github.com/redundante3452/deportBack

Integrante C:
https://github.com/BETO1274/api-fastify.git

Mi repositorio:

https://github.com/Alejom55/Inventario-U
Tarea 1: analizar primero el proyecto

Antes de programar:

Revisa la estructura completa de Inventario-U.
Identifica todas las rutas/endpoints actuales.
Identifica qué routers, servicios, schemas, modelos y acceso a base de datos utilizan.
Revisa si ya existe trabajo relacionado con /api/v2.
No elimines ni reemplaces código funcional de la versión actual.

Si ya existe una implementación parcial de V2, continúa sobre ella en vez de crear otra distinta.

Tarea 2: crear/completar API V2

Quiero que todos los endpoints funcionales relevantes de mi API queden disponibles también bajo:

/api/v2/...

Por ejemplo, si actualmente existen rutas equivalentes a:

/skus
/almacenes
/movimientos
/inventario/query

deben quedar disponibles mediante rutas versionadas como:

/api/v2/skus
/api/v2/almacenes
/api/v2/movimientos
/api/v2/inventario/query

Conserva los métodos HTTP correspondientes (GET, POST, PUT, DELETE, etc.) que ya tenga el proyecto.

No dupliques toda la implementación. Idealmente los routers V2 deben reutilizar la lógica existente.

También agrega:

GET /api/v2/health

con una respuesta similar a:

{
  "status": "ok",
  "version": "2.0.0",
  "service": "inventario-u"
}
Tarea 3: preparar integración con las APIs de los compañeros

La API V2 debe incorporar en tiempo real al menos una entidad perteneciente a cada uno de los otros dos integrantes.

No se permite:

copiar sus tablas a mi base de datos;
copiar su lógica;
guardar copias permanentes de sus entidades;
quemar respuestas JSON;
utilizar datos falsos como sustituto de las llamadas HTTP.

Los datos tienen que obtenerse haciendo solicitudes HTTP reales a las APIs propietarias.

Revisa los repositorios de los compañeros para identificar los endpoints V2 disponibles y las entidades adecuadas.

Como referencia, las entidades que inicialmente queremos utilizar son:

deportBack → Deportista
api-fastify → Artículo

Pero confirma primero en sus repositorios cuáles son los nombres de rutas y estructuras reales. No inventes endpoints.

Tarea 4: configuración mediante variables de entorno

La dirección de las APIs externas no debe estar hardcodeada.

Utiliza variables de entorno similares a:

DEPORTBACK_API_URL=
FASTIFY_API_URL=

Actualiza también .env.example, pero nunca agregues credenciales reales al repositorio.

Crea una capa clara de clientes/servicios HTTP externos, por ejemplo:

app/
  integrations/
    deportback_client.py
    fastify_client.py

o utiliza una ubicación equivalente que encaje mejor con la arquitectura existente.

Si el proyecto ya sigue otro patrón, conserva ese patrón.

Tarea 5: endpoint de integración

Crea un endpoint V2 que permita demostrar que mi API puede combinar una entidad propia con las entidades de los dos compañeros.

Puede ser algo equivalente a:

GET /api/v2/integracion

o:

POST /api/v2/flujo

Escoge el diseño que mejor encaje con la API actual y explícame por qué.

El resultado debe contener conceptualmente:

{
  "trace_id": "...",
  "inventario": {},
  "deportista": {},
  "articulo": {}
}

Los nombres exactos pueden ajustarse a los modelos reales.

inventario debe proceder de mi propia API/base de datos.

deportista debe venir mediante HTTP desde deportBack.

articulo debe venir mediante HTTP desde api-fastify.

Tarea 6: Trace ID

Necesito comenzar a cumplir el requisito de trazabilidad entre las tres nubes.

Implementa un identificador de correlación.

Usa preferiblemente:

X-Trace-Id

Comportamiento esperado:

Si la petición entrante ya contiene X-Trace-Id, conservarlo.
Si no contiene uno, generar un UUID.
Incluirlo en la respuesta.
Propagar exactamente el mismo X-Trace-Id cuando se invoque deportBack.
Propagar exactamente el mismo X-Trace-Id cuando se invoque api-fastify.
Incorporarlo en los logs relevantes.

Diseña esto de manera reutilizable, preferiblemente mediante middleware o el mecanismo equivalente adecuado para FastAPI.

Tarea 7: manejo correcto de fallos externos

Las APIs externas pueden estar caídas.

No quiero que un timeout produzca simplemente un error interno sin explicación.

Implementa:

timeout HTTP razonable;
manejo de errores de conexión;
manejo de respuestas 4xx;
manejo de respuestas 5xx;
mensajes de error útiles;
logs con trace_id.

No implementes todavía Redis, cola ni Kubernetes dentro de este cambio.

Tarea 8: evitar llamadas circulares

Ten cuidado con dependencias entre APIs.

Los endpoints que utilizamos como fuente de una entidad deberían devolver principalmente la entidad propietaria.

Evita diseñar algo como:

Inventario-U
→ deportBack
→ Inventario-U
→ deportBack
→ ...

Si descubres que alguno de los endpoints actuales de los compañeros genera ese problema, no inventes una solución silenciosamente. Identifica el problema y propón qué endpoint propietario debería utilizarse.

Tarea 9: pruebas

Crea o actualiza pruebas para comprobar como mínimo:

/api/v2/health.
Uno o varios endpoints propios bajo /api/v2.
Generación automática del X-Trace-Id.
Conservación de un X-Trace-Id recibido.
Propagación del trace ID a las llamadas HTTP externas.
Respuesta correcta cuando las APIs externas funcionan.
Comportamiento controlado cuando una API externa falla.

Para las pruebas de APIs externas utiliza mocks; las pruebas automatizadas no deben depender de que los servidores de mis compañeros estén disponibles.

Ejecuta al terminar todos los tests existentes para verificar que no rompiste la primera versión.

Restricciones importantes
No borres la API anterior.
No hagas cambios destructivos en la base de datos sin necesidad.
No cambies tecnologías del proyecto.
No añadas una segunda arquitectura paralela si no hace falta.
No hardcodees URLs.
No hardcodees secretos.
No copies entidades de los compañeros a mi BD.
No modifiques los repositorios de mis compañeros.
No implementes todavía Oracle Cloud, OKE, Redis, Object Storage ni la cola.
Mantén compatibilidad con Docker.
Respeta el estilo, formateador, tipado y herramientas que ya utiliza el repositorio.
Versionamiento

Este trabajo corresponde a la versión:

2.0.0

La entrega exige GitMoji y versionamiento semántico, pero no hagas commits ni pushes automáticamente.

Al finalizar, dime qué commits me recomiendas realizar usando GitMoji.

Por ejemplo:

✨ feat: add versioned api v2 routes
✨ feat: integrate external companion APIs
✨ feat: propagate correlation trace id
✅ test: add api v2 integration tests
Forma de trabajar

No quiero únicamente código de ejemplo.

Quiero que:

inspecciones el repositorio;
me expliques brevemente qué encontraste;
plantees los cambios concretos;
implementes los cambios directamente en los archivos correspondientes;
ejecutes las pruebas;
corrijas los errores introducidos por tus cambios;
al terminar me entregues un resumen de archivos modificados y cómo probarlo localmente.

Antes de crear código nuevo, busca si ya existe una función, servicio, dependencia o patrón reutilizable.

Prioriza cambios pequeños, claros y mantenibles.