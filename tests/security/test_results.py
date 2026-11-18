from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from app.security_results import install_security_results


def test_private_result_publication_keeps_missing_detection_censored(monkeypatch):
    monkeypatch.setenv('SECURITY_RESULTS_ENABLED','true');monkeypatch.setenv('RESOURCE_ADMIN_KEY','operator-test-only')
    monkeypatch.setenv('CHAOS_ROUND','R0')
    app=FastAPI();install_security_results(app);client=TestClient(app)
    payload={'round':'R0','execution_id':'a'*32,'scope_sha256':'b'*64,'mttd_seconds':None,'mttc_seconds':None,
        'detection_coverage_percent':0,'false_positive_percent':0,'adverse_acceptance_percent':100}
    assert client.post('/api/v2/admin/security-result',json=payload).status_code==401
    headers={'X-Api-Key':'operator-test-only'}
    assert client.post('/api/v2/admin/security-result',headers=headers,json=payload).status_code==200
    metrics=generate_latest().decode()
    assert 'inventory_security_mttd_seconds{round="R0"} NaN' in metrics
    assert 'inventory_security_mttd_seconds_observed{round="R0"} 0.0' in metrics
    assert client.post('/api/v2/admin/security-result',headers=headers,json={**payload,'mttd_seconds':5}).status_code==409


def test_negative_values_and_wrong_round_cannot_be_published(monkeypatch):
    monkeypatch.setenv('SECURITY_RESULTS_ENABLED','true');monkeypatch.setenv('RESOURCE_ADMIN_KEY','operator-test-only')
    monkeypatch.setenv('CHAOS_ROUND','R1')
    app=FastAPI();install_security_results(app);client=TestClient(app);headers={'X-Api-Key':'operator-test-only'}
    payload={'round':'R1','execution_id':'a'*32,'scope_sha256':'b'*64,'mttd_seconds':-1,'mttc_seconds':0.1,
        'detection_coverage_percent':100,'false_positive_percent':0,'adverse_acceptance_percent':0}
    assert client.post('/api/v2/admin/security-result',headers=headers,json=payload).status_code==400
    assert client.post('/api/v2/admin/security-result',headers=headers,json={**payload,'mttd_seconds':2,'round':'R0'}).status_code==400
