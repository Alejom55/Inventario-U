import json
import logging

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.observability import JsonFormatter


def test_skus_is_terminal_and_never_calls_companions(monkeypatch):
    import app.main as main
    def forbidden(*args,**kwargs):
        raise AssertionError('Terminal SKU endpoint called another API')
    monkeypatch.setattr(main,'obtener_deportista',forbidden)
    monkeypatch.setattr(main,'obtener_articulo',forbidden)
    class Database:
        def execute(self,statement):
            assert 'FROM skus' in statement
            return self
        def fetchall(self):
            return [{'id':1,'codigo':'SYNTHETIC','nombre':'Fixture','stock_minimo':0}]
    app.dependency_overrides[get_db]=lambda:Database()
    monkeypatch.delenv('TEAM_API_KEY',raising=False)
    try:
        response=TestClient(app).get('/api/v2/skus',headers={'X-Trace-Id':'terminal-proof-123'})
        assert response.status_code==200 and response.json()[0]['id']==1
        assert response.headers['X-Trace-Id']=='terminal-proof-123'
    finally:
        app.dependency_overrides.pop(get_db,None)


def test_all_application_logs_include_round_and_execution(monkeypatch):
    monkeypatch.setenv('CHAOS_ROUND','R1')
    monkeypatch.setenv('CHAOS_EXECUTION_ID','a'*32)
    record=logging.LogRecord('app.main',logging.INFO,'',1,'Solicitud recibida',(),None)
    record.trace_id='correlated-123'
    result=json.loads(JsonFormatter().format(record))
    assert result['round']=='R1' and result['execution_id']=='a'*32
    assert result['trace_id']=='correlated-123'
