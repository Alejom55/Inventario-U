from copy import deepcopy
from datetime import datetime, timezone

import pytest

from deploy.digitalocean.guard import step, validate


def state():
    return {'droplet_id':12345,'name':'inventario-chaos-abcdef123456',
        'ownership_tag':'inventario-chaos-abcdef123456','created_at':'2026-11-17T18:00:00Z',
        'delete_at':'2026-11-17T19:50:00Z','price_hourly_usd':.03571}


def test_waits_without_accessing_or_changing_cloud():
    def forbidden(*args):raise AssertionError('Early cloud action')
    assert step(state(),'test-only',datetime(2026,11,17,19,tzinfo=timezone.utc),api=forbidden)=='waiting'


def test_only_deletes_owned_resource_and_requires_absence_confirmation():
    value=state(); calls=[]
    def api(token,method,identifier):
        calls.append((method,identifier))
        return {'droplet':{'id':identifier,'name':value['name'],'tags':[value['ownership_tag']],
            'created_at':value['created_at']}} if method=='GET' else None
    assert step(value,'test-only',datetime(2026,11,17,20,tzinfo=timezone.utc),api=api)=='delete_requested'
    assert calls==[('GET',12345),('DELETE',12345)]
    assert step(value,'test-only',datetime(2026,11,17,20,tzinfo=timezone.utc),
        api=lambda *args:{'not_found':True})=='destroyed'


@pytest.mark.parametrize('field,value',[('id',999),('name','other-project'),('tags',[]),('created_at','2026-11-16T18:00:00Z')])
def test_never_deletes_unrelated_droplet(field,value):
    original=state(); droplet={'id':12345,'name':original['name'],'tags':[original['ownership_tag']],
        'created_at':original['created_at']};droplet[field]=value
    def api(token,method,identifier):
        assert method=='GET'
        return {'droplet':droplet}
    with pytest.raises(RuntimeError,match='Ownership mismatch'):
        step(original,'test-only',datetime(2026,11,17,20,tzinfo=timezone.utc),api=api)


@pytest.mark.parametrize('change',[{'price_hourly_usd':1},{'price_hourly_usd':float('nan')},
    {'delete_at':'2026-11-17T21:00:00Z'},{'droplet_id':'12345'},{'ownership_tag':'unrelated'}])
def test_rejects_cost_window_or_scope_outside_authorization(change):
    value=deepcopy(state());value.update(change)
    with pytest.raises(ValueError):validate(value)
