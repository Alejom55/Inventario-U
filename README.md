# Gestor de inventario

API para administrar inventario entre varios almacenes.

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
3. No subas `.env` al repositorio: contiene valores específicos de cada ambiente.

## Consulta de inventario con HTTP QUERY

La API admite el método HTTP `QUERY` en `/inventario/query`. Este método solo consulta: no crea, modifica ni elimina datos.

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
curl -X QUERY http://127.0.0.1:8000/inventario/query \
  -H "Content-Type: application/json" \
  -d "{\"almacen_id\": 1, \"solo_stock_bajo\": true}"
```

Puedes verificar los formatos aceptados con:

```bash
curl -X OPTIONS -i http://127.0.0.1:8000/inventario/query
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
