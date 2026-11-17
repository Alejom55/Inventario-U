import json

import pytest

from deploy.local_team.content import contract, guide, postman, public_gateway
from scripts import local_team


def values():
    return {name:character*48 for name,character in zip(('TEAM_API_KEY','PEER_API_KEY','METRICS_TOKEN','POSTGRES_PASSWORD','GRAFANA_PASSWORD','VIEWER_PASSWORD'),'abcdef')}


def test_public_artifacts_never_embed_credentials(tmp_path,monkeypatch):
    monkeypatch.setattr(local_team,'RUNTIME',tmp_path)
    secrets=values()
    local_team.configure(secrets,'https://example-team.trycloudflare.com',{'sku_id':1,'almacen_id':2})
    for folder in ('exports','dashboards'):
        for path in (tmp_path/folder).glob('*'):
            assert all(value not in path.read_text(encoding='utf-8') for key,value in secrets.items() if key.endswith(('KEY','TOKEN','PASSWORD')))
    imported=json.loads((tmp_path/'exports/dashboard.json').read_text())
    assert imported['__inputs'][0]['name']=='DS_PROMETHEUS'


@pytest.mark.parametrize('base',['https://other.example','http://example-team.trycloudflare.com','https://user:password@example-team.trycloudflare.com'])
def test_unknown_tunnel_urls_rejected_before_writing(base,tmp_path,monkeypatch):
    monkeypatch.setattr(local_team,'RUNTIME',tmp_path)
    with pytest.raises(ValueError):local_team.configure(values(),base,{})
    assert not list(tmp_path.iterdir())


def test_template_injection_rejected():
    secrets=values();secrets['PEER_API_KEY']='x"; return 200;'
    with pytest.raises(ValueError):public_gateway(secrets)


def test_contract_and_postman_use_same_ids_and_body():
    base='https://example-team.trycloudflare.com';ids={'sku_id':7,'almacen_id':9}
    schema=contract(base,ids);collection=postman(base,ids)
    assert schema['inventory']['query']==ids
    assert json.loads(collection['item'][2]['request']['body']['raw'])==ids
    assert 'dependencia circular' in guide(base,ids)
    assert collection['variable'][1]['value']==''
    assert schema['terminal_dependency']['calls_peer_apis'] is False
    assert 'no llama a deport-back ni api-fastify' in guide(base,ids)
