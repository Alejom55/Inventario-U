import asyncio

import anyio
import pytest
from fastapi import HTTPException

from app.resource_lab import ResourceFault
from app.resource_lab import install_resource_lab


@pytest.mark.parametrize('protected,admitted',[(False,6),(True,4)])
def test_real_worker_exhaustion_and_rollback(protected,admitted):
    async def check():
        limiter=anyio.to_thread.current_default_thread_limiter()
        limiter.total_tokens=6
        state=ResourceFault(protected,'R1' if protected else 'R0')
        try:
            result=await state.inject(6,2)
            assert result['admitted']==admitted and result['rejected']==6-admitted
            assert limiter.borrowed_tokens==(0 if protected else 6)
            with pytest.raises(HTTPException) as exc:
                await state.inject(6,2)
            assert exc.value.status_code==409
        finally:
            assert (await state.release())['rollback_verified']
        assert limiter.borrowed_tokens==0
    asyncio.run(check())


def test_private_switch_authentication_and_bounds(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    monkeypatch.setenv('RESOURCE_LAB_ENABLED','true')
    monkeypatch.setenv('TEAM_API_KEY','private-test-only')
    app=FastAPI()
    @app.middleware('http')
    async def trace(request,call_next):
        request.state.trace_id='unit-trace'
        return await call_next(request)
    install_resource_lab(app)
    path='/api/v2/admin/resource-fault'
    with TestClient(app) as client:
        assert client.post(path,json={'workers':6,'duration_seconds':1}).status_code==401
        headers={'X-Api-Key':'private-test-only'}
        assert client.post(path,headers=headers,json={'workers':7,'duration_seconds':61}).status_code==400
        assert client.post(path,headers=headers,json={'workers':6,'duration_seconds':1}).status_code==200
        assert client.get(path,headers=headers).json()['active']==6
        assert client.delete(path,headers=headers).json()['rollback_verified']


def test_shared_api_does_not_install_resource_controls(monkeypatch):
    from fastapi import FastAPI
    monkeypatch.delenv('RESOURCE_LAB_ENABLED',raising=False)
    app=FastAPI()
    install_resource_lab(app)
    assert not any('resource-fault' in route.path for route in app.routes)


def test_fault_expires_without_controller():
    async def check():
        state=ResourceFault(False,'R0')
        await state.inject(2,1)
        await asyncio.sleep(1.1)
        assert not state.tasks
    asyncio.run(check())
