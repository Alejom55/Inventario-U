# Gestor de inventario

API para administrar inventario entre varios almacenes.

## Versionamiento

La API original se conserva sin prefijo (`/skus`, `/almacenes`, `/movimientos`
e `/inventario/query`). La versión 2 expone las mismas operaciones bajo
`/api/v2` y añade trazabilidad e integración externa.

`GET /api/v2/health` responde:

```json
{
  "status": "ok",
  "version": "2.0.0",
  "service": "inventario-u"
}
```

## Objetivo

Construir una API RESTful con persistencia real que permita administrar productos, almacenes y movimientos de inventario. El proyecto incluirá el método HTTP `QUERY` para realizar consultas complejas de inventario sin modificar datos.

## Entidades

### SKU

Representa un producto identificable en el inventario.

- Código SKU
- Nombre
- Descripción
- Stock mínimo

### Almacén

Representa la ubicación física donde se guardan productos.

- Nombre
- Ubicación

### Movimiento

Registra una entrada, salida o ajuste de un SKU en un almacén.

- SKU
- Almacén
- Tipo de movimiento
- Cantidad
- Fecha y motivo

## Ejecución local

Para iniciar la estructura inicial de FastAPI:

```bash
uv sync
uv run fastapi dev app/main.py
```

La guía con PostgreSQL y Docker se completará más adelante. El comando final será:

```bash
docker compose up --build
```

## Configuración de base de datos

1. Copia `.env.example` como `.env`.
2. Ajusta `DATABASE_URL` con las credenciales de tu PostgreSQL local.
3. Define `DEPORTBACK_API_URL` y `FASTIFY_API_URL` con las URL base de los
   servicios de los compañeros.
4. Define `TEAM_API_KEY` solo cuando el equipo haya acordado una clave compartida.
   Si está vacía, la API queda abierta para desarrollo local.
5. No subas `.env` al repositorio: contiene valores específicos de cada ambiente.

## Integración V2 y trazabilidad

`GET /api/v2/integracion` combina un inventario local con un deportista y un
artículo obtenidos en tiempo real desde sus APIs propietarias. Requiere los
parámetros `sku_id`, `almacen_id`, `deportista_id` y `articulo_id`.

```bash
curl "http://127.0.0.1:8000/api/v2/integracion?sku_id=1&almacen_id=1&deportista_id=<uuid>&articulo_id=1" \
  -H "X-Trace-Id: demo-123"
```

La respuesta conserva o genera `X-Trace-Id`, lo devuelve en el encabezado y
en el cuerpo, y lo reenvía a ambos servicios externos. Si alguno falla o se
agota el tiempo de espera, el endpoint responde `502` con el servicio y la
causa; no persiste los datos externos.

Mientras los contratos propietarios V2 de los compañeros están pendientes, la
integración consulta temporalmente `/deportistas/{id}` y `/articulos/{id}`.
Estas rutas no se cambiarán hasta que los endpoints equivalentes bajo
`/api/v2` estén disponibles y no introduzcan ciclos.

Cuando `TEAM_API_KEY` está configurada, las rutas funcionales V1 y V2 requieren
el encabezado `X-Api-Key`. Los endpoints `/health` y `/api/v2/health` siempre
permanecen públicos para probes. Las llamadas externas propagan tanto
`X-Api-Key` como `X-Trace-Id`.

## Consulta de inventario con HTTP QUERY

La API admite el método HTTP `QUERY` en `/inventario/query` y
`/api/v2/inventario/query`. Este método solo consulta: no crea, modifica ni elimina datos.

Envía un body JSON con filtros opcionales:

```json
{
  "sku_id": 1,
  "almacen_id": 1,
  "tipo": "salida",
  "fecha_desde": "2026-08-01T00:00:00",
  "fecha_hasta": "2026-08-31T23:59:59",
  "solo_stock_bajo": false
}
```

El resultado muestra el stock total disponible de cada SKU por almacén. Si filtras por tipo o fecha, se muestran únicamente las combinaciones que tengan movimientos que coincidan con ese filtro, pero el stock sigue calculándose con todo el historial.

```bash
curl -X QUERY http://127.0.0.1:8000/api/v2/inventario/query \
  -H "Content-Type: application/json" \
  -d "{\"almacen_id\": 1, \"solo_stock_bajo\": true}"
```

Puedes verificar los formatos aceptados con:

```bash
curl -X OPTIONS -i http://127.0.0.1:8000/api/v2/inventario/query
```

La respuesta incluye el encabezado `Accept-Query: application/json`.

## Pruebas automatizadas

Las pruebas usan una base de datos aislada indicada por `TEST_DATABASE_URL`. Crea primero esa base en PostgreSQL y verifica que su nombre sea diferente de la usada en `DATABASE_URL`.

```bash
uv sync --group dev
uv run python scripts/create_test_database.py
uv run pytest
```

La cobertura se muestra al terminar y debe ser al menos 85%. Para el futuro pipeline de pruebas se podrá permitir un mínimo de 60%, mientras que producción exigirá 85%.

## Docker

Docker Compose levanta dos servicios: la API y PostgreSQL. La base de datos se mantiene en el volumen `postgres_data`.

```bash
docker compose up --build
```

Cuando ambos contenedores estén listos, comprueba la API:

```bash
curl http://127.0.0.1:8000/api/v2/health
```

Para detener los contenedores:

```bash
docker compose down
```
