def test_get_matches_query_and_preserves_trace(client):
    sku = client.post('/api/v2/skus', json={'codigo':'GET-TEST','nombre':'GET test','stock_minimo':3}).json()
    warehouse = client.post('/api/v2/almacenes', json={'nombre':'GET test','ubicacion':'Sintetico'}).json()
    ids = {'sku_id':sku['id'], 'almacen_id':warehouse['id']}
    assert client.post('/api/v2/movimientos',json={**ids,'tipo':'entrada','cantidad':8,'motivo':'GET test'}).status_code==201
    response = client.get('/api/v2/inventario',params=ids,headers={'X-Trace-Id':'peer-trace-123'})
    original = client.request('QUERY','/api/v2/inventario/query',json=ids)
    assert response.status_code==200 and response.json()==original.json()
    assert response.json()['resultados'][0]['stock_disponible']==8
    assert response.headers['X-Trace-Id']=='peer-trace-123'
    assert client.get('/api/v2/inventario',params={'sku_id':0,'almacen_id':1}).status_code==422
    assert client.get('/api/v2/inventario').status_code==422
