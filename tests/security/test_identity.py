import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient
import jwt
import pytest

from app.observability import JsonFormatter
from app.security_identity import IdentityPolicy


@pytest.fixture
def material(tmp_path):
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    path=tmp_path/'public.pem';path.write_bytes(public)
    policy=IdentityPolicy(mode='workload',public_key=public.decode(),subjects=('deport-back',),
        honeytoken_hash=hashlib.sha256(b'decoy-test-only').hexdigest())
    return private,path,policy


def token(material,**changes):
    now=int(time.time())-1
    claims={'iss':'inventario-u-security-lab','aud':'inventario-u','sub':'deport-back',
        'iat':now,'nbf':now,'exp':now+60,'jti':uuid4().hex,'scope':'inventory:read'}
    claims.update(changes)
    return jwt.encode(claims,material[0],algorithm='EdDSA')


def client_for(policy):
    app=FastAPI()
    @app.middleware('http')
    async def protect(request,call_next):
        request.state.trace_id='security-unit-trace'
        denial=policy.authorize(request)
        return denial if denial is not None else await call_next(request)
    @app.get('/fixture')
    async def read():return {'synthetic':True}
    @app.post('/fixture')
    async def write():return {'synthetic':True}
    return TestClient(app)


def test_valid_workload_reads_but_cannot_use_read_token_to_write(material):
    client=client_for(material[2]);headers={'Authorization':'Bearer '+token(material)}
    assert client.get('/fixture',headers=headers).status_code==200
    response=client.post('/fixture',headers=headers)
    assert response.status_code==403 and response.json()['reason']=='scope_violation'
    assert response.headers['X-Trace-Id']=='security-unit-trace'


def test_explicit_write_scope_is_required(material):
    client=client_for(material[2])
    assert client.post('/fixture',headers={'Authorization':'Bearer '+token(material,scope='inventory:write')}).status_code==200


@pytest.mark.parametrize('changes,reason',[
    ({'aud':'another-api'},'wrong_audience'),
    ({'aud':['inventario-u','another-api']},'wrong_audience'),
    ({'iss':'another-issuer'},'wrong_issuer'),
    ({'sub':'unknown-agent'},'unknown_subject'),
    ({'scope':'admin'},'scope_violation'),
    ({'scope':None},'invalid_token'),
    ({'scope':0},'invalid_scope'),
    ({'exp':int(time.time())-30},'expired'),
    ({'exp':int(time.time())+900},'invalid_lifetime_or_id'),
    ({'jti':'unsafe-id'},'invalid_lifetime_or_id'),
])
def test_adverse_identity_cases_have_bounded_detection_reasons(material,changes,reason):
    response=client_for(material[2]).get('/fixture',headers={'Authorization':'Bearer '+token(material,**changes)})
    assert response.status_code in (401,403) and response.json()['reason']==reason


def test_static_api_key_cannot_bypass_workload_policy(material):
    response=client_for(material[2]).get('/fixture',headers={'X-Api-Key':'static-test-only'})
    assert response.status_code==401


def test_decoy_never_grants_access_and_has_a_dedicated_signal(material):
    response=client_for(material[2]).get('/fixture',headers={'Authorization':'Bearer decoy-test-only'})
    assert response.status_code==401 and response.json()['reason']=='honeytoken'


def test_wrong_signing_key_and_algorithm_are_rejected(material):
    wrong=Ed25519PrivateKey.generate()
    claims={'iss':'inventario-u-security-lab','aud':'inventario-u'}
    for encoded in (jwt.encode(claims,wrong,algorithm='EdDSA'),jwt.encode(claims,'test-only-secret-long-enough-for-hmac',algorithm='HS256')):
        assert client_for(material[2]).get('/fixture',headers={'Authorization':'Bearer '+encoded}).json()['reason']=='invalid_token'


def test_audit_redacts_tokens_and_has_positive_and_negative_signals(material,caplog):
    caplog.set_level(logging.INFO,logger='app.security_identity')
    client=client_for(material[2]);encoded=token(material)
    assert client.get('/fixture',headers={'Authorization':'Bearer '+encoded}).status_code==200
    assert not [r for r in caplog.records if getattr(r,'event',None)=='security_identity_detected']
    assert client.post('/fixture',headers={'Authorization':'Bearer '+encoded}).status_code==403
    rows=[json.loads(JsonFormatter().format(r)) for r in caplog.records]
    detections=[r for r in rows if r.get('event')=='security_identity_detected']
    assert len(detections)==1 and detections[0]['reason']=='scope_violation'
    assert detections[0]['trace_id']=='security-unit-trace' and 'round' in detections[0]
    assert encoded not in json.dumps(rows)


def test_workload_configuration_fails_closed_and_requires_public_key(material,monkeypatch,tmp_path):
    monkeypatch.setenv('SECURITY_AUTH_MODE','workload')
    monkeypatch.delenv('SECURITY_JWT_PUBLIC_KEY_FILE',raising=False)
    with pytest.raises(ValueError):IdentityPolicy.from_environment()
    monkeypatch.setenv('SECURITY_JWT_PUBLIC_KEY_FILE',str(material[1]))
    monkeypatch.setenv('SECURITY_ALLOWED_SUBJECTS','deport-back')
    assert IdentityPolicy.from_environment().subjects==('deport-back',)
    private=tmp_path/'private.pem'
    private.write_bytes(material[0].private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    monkeypatch.setenv('SECURITY_JWT_PUBLIC_KEY_FILE',str(private))
    with pytest.raises(ValueError,match='public verification'):IdentityPolicy.from_environment()


def test_real_api_does_not_fall_back_to_static_business_key(material):
    env=dict(os.environ,SECURITY_AUTH_MODE='workload',SECURITY_JWT_PUBLIC_KEY_FILE=str(material[1]),
        SECURITY_ALLOWED_SUBJECTS='deport-back',TEAM_API_KEY='old-test-key',RESOURCE_LAB_ENABLED='false')
    script="from app.main import app; from fastapi.testclient import TestClient; c=TestClient(app); assert c.get('/api/v2/unknown',headers={'X-Api-Key':'old-test-key'}).status_code==401; assert c.get('/health').status_code==200"
    result=subprocess.run([sys.executable,'-c',script],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
