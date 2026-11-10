from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import pytest

from chaos_lab import providers


@pytest.fixture
def configuration():
    now = datetime.now(timezone.utc)
    return {"window_ack": "GROUP_SYNTHETIC_ONLY", "toxiproxy_url": "http://127.0.0.1:8474", "prometheus_url": "http://localhost:9090", "proxy_name": "chaos-deportback", "expected_upstream": "peer.test:8000", "round": "R0", "run_id": "a"*32, "window_start_utc": (now-timedelta(minutes=1)).isoformat(), "window_end_utc": (now+timedelta(minutes=10)).isoformat(), "max_p95_seconds": "0.5"}


@pytest.mark.parametrize('field,value', [('window_ack', ''), ('toxiproxy_url','http://public.example'), ('toxiproxy_url','http://user:password@localhost:8474'), ('prometheus_url','http://localhost:9090?x=1'), ('proxy_name','stable'), ('round','unknown'), ('max_p95_seconds','nan')])
def test_scope_rejects_unsafe_or_ambiguous_configuration(configuration, field, value):
    configuration[field] = value
    with pytest.raises(ValueError):
        providers.validate_scope(configuration)


def test_expired_window_prevents_injection(configuration, monkeypatch):
    configuration['window_end_utc'] = configuration['window_start_utc']
    calls = []
    monkeypatch.setattr(providers, 'request_json', lambda *args: calls.append(args))
    with pytest.raises(ValueError, match='window'):
        providers.inject_latency(configuration)
    assert not calls


@pytest.mark.parametrize('total,success,p95,expected', [(120,120,.2,True),(120,0,.01,False),(12,12,.2,False),(120,120,2,False)])
def test_gate_rejects_fast_errors_and_insufficient_samples(configuration,monkeypatch,total,success,p95,expected):
    values = iter([total,success,p95])
    monkeypatch.setattr(providers,'prometheus_value',lambda *args:next(values))
    assert providers.within_objective(configuration) is expected


def test_injection_only_modifies_selected_empty_proxy(configuration, monkeypatch):
    calls = []
    def request(url, method='GET', body=None):
        calls.append((url,method,body))
        return {'upstream':'peer.test:8000','enabled':True,'toxics':[]} if method=='GET' else body
    monkeypatch.setattr(providers,'request_json',request)
    result=providers.inject_latency(configuration)
    assert result['attributes']['latency']==1500
    assert calls[-1][0].endswith('/proxies/chaos-deportback/toxics')


def test_existing_toxics_prevent_injection(configuration,monkeypatch):
    monkeypatch.setattr(providers,'request_json',lambda *args:{'upstream':'peer.test:8000','enabled':True,'toxics':[{'name':'someone-elses-fault'}]})
    with pytest.raises(ValueError):providers.inject_latency(configuration)


def test_cleanup_works_after_window_expiry_and_is_idempotent(configuration,monkeypatch):
    configuration['window_end_utc']=configuration['window_start_utc']
    calls=[]
    def request(url,method='GET',body=None):
        calls.append((url,method))
        if method=='DELETE':raise HTTPError(url,404,'already removed',None,None)
        return {'upstream':'peer.test:8000','toxics':[]}
    monkeypatch.setattr(providers,'request_json',request)
    assert providers.remove_latency(configuration)
    assert all('/reset' not in url for url,_ in calls)
