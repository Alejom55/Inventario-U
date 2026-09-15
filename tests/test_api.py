def crear_sku(client, codigo="SKU-001", nombre="Teclado", stock_minimo=2):
    respuesta = client.post(
        "/skus",
        json={
            "codigo": codigo,
            "nombre": nombre,
            "descripcion": "Producto de prueba",
            "stock_minimo": stock_minimo,
        },
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def crear_almacen(client, nombre="Principal", ubicacion="Bogotá"):
    respuesta = client.post(
        "/almacenes",
        json={"nombre": nombre, "ubicacion": ubicacion},
    )
    assert respuesta.status_code == 201
    return respuesta.json()


def crear_movimiento(client, sku_id, almacen_id, tipo, cantidad, motivo="Prueba"):
    return client.post(
        "/movimientos",
        json={
            "sku_id": sku_id,
            "almacen_id": almacen_id,
            "tipo": tipo,
            "cantidad": cantidad,
            "motivo": motivo,
        },
    )


def test_estado_de_la_api(client):
    respuesta = client.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


def test_crud_sku(client):
    sku = crear_sku(client)

    respuesta = client.get("/skus")
    assert respuesta.status_code == 200
    assert respuesta.json() == [sku]

    respuesta = client.get(f"/skus/{sku['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["codigo"] == "SKU-001"

    respuesta = client.put(
        f"/skus/{sku['id']}",
        json={
            "codigo": "SKU-002",
            "nombre": "Teclado mecánico",
            "descripcion": None,
            "stock_minimo": 4,
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["codigo"] == "SKU-002"

    respuesta = client.delete(f"/skus/{sku['id']}")
    assert respuesta.status_code == 204
    assert client.get(f"/skus/{sku['id']}").status_code == 404


def test_validaciones_sku(client):
    crear_sku(client)

    respuesta = client.post(
        "/skus",
        json={"codigo": "SKU-001", "nombre": "Duplicado", "stock_minimo": 0},
    )
    assert respuesta.status_code == 409

    respuesta = client.post(
        "/skus",
        json={"codigo": "", "nombre": "Inválido", "stock_minimo": -1},
    )
    assert respuesta.status_code == 400

    respuesta = client.put(
        "/skus/999",
        json={"codigo": "SKU-999", "nombre": "No existe", "stock_minimo": 0},
    )
    assert respuesta.status_code == 404

    assert client.delete("/skus/999").status_code == 404


def test_crud_almacen(client):
    almacen = crear_almacen(client)

    respuesta = client.get("/almacenes")
    assert respuesta.status_code == 200
    assert respuesta.json() == [almacen]

    respuesta = client.get(f"/almacenes/{almacen['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["ubicacion"] == "Bogotá"

    respuesta = client.put(
        f"/almacenes/{almacen['id']}",
        json={"nombre": "Secundario", "ubicacion": "Medellín"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["nombre"] == "Secundario"

    assert client.delete(f"/almacenes/{almacen['id']}").status_code == 204
    assert client.get(f"/almacenes/{almacen['id']}").status_code == 404


def test_validaciones_almacen(client):
    crear_almacen(client)

    respuesta = client.post(
        "/almacenes", json={"nombre": "Principal", "ubicacion": "Cali"}
    )
    assert respuesta.status_code == 409

    respuesta = client.post("/almacenes", json={"nombre": "", "ubicacion": ""})
    assert respuesta.status_code == 400

    respuesta = client.put("/almacenes/999", json={"nombre": "X", "ubicacion": "Y"})
    assert respuesta.status_code == 404

    assert client.delete("/almacenes/999").status_code == 404


def test_movimientos_y_filtros(client):
    sku = crear_sku(client)
    almacen = crear_almacen(client)

    entrada = crear_movimiento(client, sku["id"], almacen["id"], "entrada", 10)
    assert entrada.status_code == 201
    salida = crear_movimiento(client, sku["id"], almacen["id"], "salida", 3)
    assert salida.status_code == 201
    ajuste = crear_movimiento(client, sku["id"], almacen["id"], "ajuste", -1)
    assert ajuste.status_code == 201

    respuesta = client.get(
        f"/movimientos?sku_id={sku['id']}&almacen_id={almacen['id']}&tipo=salida"
    )
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 1
    assert respuesta.json()[0]["tipo"] == "salida"

    respuesta = client.get(f"/movimientos/{entrada.json()['id']}")
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad"] == 10


def test_actualizar_y_eliminar_movimiento(client):
    sku = crear_sku(client)
    almacen = crear_almacen(client)
    movimiento = crear_movimiento(client, sku["id"], almacen["id"], "entrada", 10).json()

    respuesta = client.put(
        f"/movimientos/{movimiento['id']}",
        json={
            "sku_id": sku["id"],
            "almacen_id": almacen["id"],
            "tipo": "entrada",
            "cantidad": 12,
            "motivo": "Corrección",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["cantidad"] == 12

    assert client.delete(f"/movimientos/{movimiento['id']}").status_code == 204
    assert client.get(f"/movimientos/{movimiento['id']}").status_code == 404


def test_reglas_de_inventario(client):
    sku = crear_sku(client)
    almacen = crear_almacen(client)

    respuesta = crear_movimiento(client, sku["id"], almacen["id"], "salida", 1)
    assert respuesta.status_code == 400

    entrada = crear_movimiento(client, sku["id"], almacen["id"], "entrada", 5).json()
    assert crear_movimiento(client, sku["id"], almacen["id"], "salida", 3).status_code == 201

    respuesta = client.delete(f"/movimientos/{entrada['id']}")
    assert respuesta.status_code == 400

    respuesta = crear_movimiento(client, 999, almacen["id"], "entrada", 1)
    assert respuesta.status_code == 404

    respuesta = crear_movimiento(client, sku["id"], almacen["id"], "otro", 1)
    assert respuesta.status_code == 400


def test_query_de_inventario(client):
    sku = crear_sku(client, stock_minimo=8)
    almacen = crear_almacen(client)
    assert crear_movimiento(client, sku["id"], almacen["id"], "entrada", 10).status_code == 201
    assert crear_movimiento(client, sku["id"], almacen["id"], "salida", 4).status_code == 201

    respuesta = client.request(
        "QUERY",
        "/inventario/query",
        json={"sku_id": sku["id"], "almacen_id": almacen["id"], "tipo": "salida"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["resultados"][0]["stock_disponible"] == 6

    respuesta = client.request(
        "QUERY",
        "/inventario/query",
        json={"solo_stock_bajo": True},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["resultados"][0]["sku_id"] == sku["id"]

    respuesta = client.request(
        "QUERY",
        "/inventario/query",
        json={"fecha_desde": "fecha-inválida"},
    )
    assert respuesta.status_code == 400

    respuesta = client.options("/inventario/query")
    assert respuesta.status_code == 200
    assert respuesta.headers["accept-query"] == "application/json"


def test_v2_salud_y_rutas_propias(client):
    respuesta = client.get("/api/v2/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "status": "ok",
        "version": "2.0.0",
        "service": "inventario-u",
    }
    assert respuesta.headers["x-trace-id"]

    sku = crear_sku(client)
    respuesta = client.get("/api/v2/skus")

    assert respuesta.status_code == 200
    assert respuesta.json() == [sku]


def test_trace_id_recibido_se_conserva(client):
    trace_id = "trace-del-cliente"

    respuesta = client.get("/api/v2/health", headers={"X-Trace-Id": trace_id})

    assert respuesta.headers["x-trace-id"] == trace_id


def test_api_key_correcta_permite_rutas_v1_y_v2(client, monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "clave-de-prueba")

    respuesta_v1 = client.get("/skus", headers={"X-Api-Key": "clave-de-prueba"})
    respuesta_v2 = client.get("/api/v2/skus", headers={"X-Api-Key": "clave-de-prueba"})

    assert respuesta_v1.status_code == 200
    assert respuesta_v2.status_code == 200


def test_api_key_incorrecta_es_rechazada(client, monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "clave-de-prueba")

    respuesta = client.get("/api/v2/skus", headers={"X-Api-Key": "clave-incorrecta"})

    assert respuesta.status_code == 401
    assert respuesta.json()["detail"] == "API key inválida o ausente"


def test_api_key_ausente_es_rechazada_y_health_permanece_publico(client, monkeypatch):
    monkeypatch.setenv("TEAM_API_KEY", "clave-de-prueba")

    respuesta = client.get("/skus")
    health_v1 = client.get("/health")
    health_v2 = client.get("/api/v2/health")

    assert respuesta.status_code == 401
    assert health_v1.status_code == 200
    assert health_v2.status_code == 200


def test_api_permanece_abierta_sin_team_api_key(client, monkeypatch):
    monkeypatch.delenv("TEAM_API_KEY", raising=False)

    respuesta = client.get("/api/v2/skus")

    assert respuesta.status_code == 200


def test_cliente_externo_omite_api_key_sin_configuracion(monkeypatch):
    from app.integrations.external_api import get_json

    headers_enviados = {}

    class RespuestaExterna:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class ClienteExterno:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, headers):
            headers_enviados.update(headers)
            return RespuestaExterna()

    monkeypatch.delenv("TEAM_API_KEY", raising=False)
    monkeypatch.setattr("app.integrations.external_api.httpx.Client", lambda timeout: ClienteExterno())

    respuesta = get_json("https://externa.test", "/recurso", "externa", "trace-sin-key")

    assert respuesta == {"ok": True}
    assert headers_enviados == {"X-Trace-Id": "trace-sin-key"}


def test_integracion_v2_propagates_trace_id(client, monkeypatch):
    sku = crear_sku(client)
    almacen = crear_almacen(client)
    llamadas = []

    class RespuestaExterna:
        def __init__(self, datos):
            self.datos = datos

        def raise_for_status(self):
            return None

        def json(self):
            return self.datos

    class ClienteExterno:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url, headers):
            llamadas.append((url, headers))
            if "/deportistas/" in url:
                return RespuestaExterna({"id": "dep-1", "nombre": "Ana"})
            return RespuestaExterna({"id": 7, "nombre": "Tornillo"})

    monkeypatch.setenv("DEPORTBACK_API_URL", "https://deportback.test")
    monkeypatch.setenv("FASTIFY_API_URL", "https://fastify.test")
    monkeypatch.setenv("TEAM_API_KEY", "clave-de-prueba")
    monkeypatch.setattr("app.integrations.external_api.httpx.Client", lambda timeout: ClienteExterno())

    respuesta = client.get(
        "/api/v2/integracion",
        params={
            "sku_id": sku["id"],
            "almacen_id": almacen["id"],
            "deportista_id": "dep-1",
            "articulo_id": 7,
        },
        headers={"X-Trace-Id": "trace-integracion", "X-Api-Key": "clave-de-prueba"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["trace_id"] == "trace-integracion"
    assert respuesta.json()["deportista"]["id"] == "dep-1"
    assert respuesta.json()["articulo"]["id"] == 7
    assert [url for url, _ in llamadas] == [
        "https://deportback.test/deportistas/dep-1",
        "https://fastify.test/articulos/7",
    ]
    assert all(headers["X-Trace-Id"] == "trace-integracion" for _, headers in llamadas)
    assert all(headers["X-Api-Key"] == "clave-de-prueba" for _, headers in llamadas)


def test_integracion_v2_controla_fallo_externo(client, monkeypatch):
    from app.integrations.external_api import ExternalApiError

    sku = crear_sku(client)
    almacen = crear_almacen(client)

    def falla_deportback(*args):
        raise ExternalApiError("deportBack", "deportBack agotó el tiempo de espera")

    monkeypatch.setattr("app.main.obtener_deportista", falla_deportback)
    respuesta = client.get(
        "/api/v2/integracion",
        params={
            "sku_id": sku["id"],
            "almacen_id": almacen["id"],
            "deportista_id": "dep-1",
            "articulo_id": 7,
        },
    )

    assert respuesta.status_code == 502
    assert respuesta.json()["detail"]["service"] == "deportBack"
    assert respuesta.headers["x-trace-id"]
