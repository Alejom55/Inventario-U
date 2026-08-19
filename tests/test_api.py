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
