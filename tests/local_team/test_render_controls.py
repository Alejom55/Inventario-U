import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.resource_lab import install_resource_lab
from app.telemetry import install_telemetry
from app.render_surface import restrict_render_surface


def make_app(monkeypatch):
    for name,value in {'RESOURCE_LAB_ENABLED':'true','TEAM_API_KEY':'business-test',
        'RESOURCE_ADMIN_KEY':'admin-test','METRICS_BEARER_TOKEN':'metrics-test',
        'CHAOS_ROUND':'none','CHAOS_EXECUTION_ID':'none','RESILIENCE_MODE':'protected'}.items():
        monkeypatch.setenv(name,value)
    app=FastAPI()
    @app.middleware('http')
    async def trace(request,call_next):
        request.state.trace_id='render-test-trace'
        return await call_next(request)
    install_resource_lab(app)
    install_telemetry(app)
    return app


def test_business_key_cannot_change_round_and_results_are_execution_bound(monkeypatch):
    app=make_app(monkeypatch);headers={'X-Api-Key':'admin-test'}
    body={'round':'R1','execution_id':'a'*32}
    with TestClient(app) as client:
        path='/api/v2/admin/resource-round'
        assert client.post(path,headers={'X-Api-Key':'business-test'},json=body).status_code==401
        assert client.post(path,headers=headers,json={**body,'round':'R2'}).status_code==400
        response=client.post(path,headers=headers,json=body)
        assert response.json()['protected'] and response.headers['X-Chaos-Round']=='R1'
        result={**body,'samples':300,'successes':299,'p95_ms':750}
        assert client.post('/api/v2/admin/resource-result',headers=headers,json={**result,'execution_id':'b'*32}).status_code==409
        assert client.post('/api/v2/admin/resource-result',headers=headers,json={**result,'successes':301}).status_code==400
        assert client.post('/api/v2/admin/resource-result',headers=headers,json=result).status_code==200
        metrics=client.get('/metrics',headers={'Authorization':'Bearer metrics-test'})
        assert 'inventory_resource_client_success_ratio{round="R1"}' in metrics.text
        assert 'inventory_resource_client_p95_seconds{round="R1"} 0.75' in metrics.text
        assert client.get('/metrics').status_code==401


def test_round_cannot_change_during_an_active_fault(monkeypatch):
    app=make_app(monkeypatch);headers={'X-Api-Key':'admin-test'}
    with TestClient(app) as client:
        assert client.post('/api/v2/admin/resource-fault',headers=headers,json={'workers':1,'duration_seconds':1}).status_code==200
        assert client.post('/api/v2/admin/resource-round',headers=headers,json={'round':'R0','execution_id':'a'*32}).status_code==409
        assert client.delete('/api/v2/admin/resource-fault',headers=headers).json()['rollback_verified']
        assert client.post('/api/v2/admin/resource-round',headers=headers,json={'round':'R0','execution_id':'a'*32}).json()['protected'] is False


def test_render_refuses_unprotected_control_credentials(monkeypatch):
    monkeypatch.setenv('RENDER','true');monkeypatch.setenv('RESOURCE_LAB_ENABLED','true')
    monkeypatch.delenv('RESOURCE_ADMIN_KEY',raising=False)
    with pytest.raises(ValueError,match='separate private control'):
        install_resource_lab(FastAPI())


def test_render_removes_storage_and_coordinator_without_hiding_business(monkeypatch):
    monkeypatch.setenv('RENDER','true')
    app=FastAPI()
    for path in ('/api/v2/storage','/api/v2/storage/{trace_id}','/api/v2/integracion','/api/v2/skus'):
        app.add_api_route(path,lambda:{'ok':True},methods=['GET'])
    restrict_render_surface(app)
    client=TestClient(app)
    assert client.get('/api/v2/skus').status_code==200
    assert client.get('/api/v2/storage').status_code==404
    assert client.get('/api/v2/storage/test').status_code==404
    assert client.get('/api/v2/integracion').status_code==404
