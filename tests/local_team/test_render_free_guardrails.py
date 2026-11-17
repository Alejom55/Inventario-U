import pytest

from deploy.render import free


def test_no_paid_service_can_be_created_before_network_access():
    with pytest.raises(ValueError,match='non-Free'):
        free.api('POST','/services',{'ownerId':free.OWNER,'serviceDetails':{'plan':'starter'}})


def test_existing_services_cannot_be_modified(monkeypatch):
    monkeypatch.setattr(free,'read',lambda *args:{'api_service_id':'owned-new','prometheus_service_id':'owned-prom','database_id':'owned-db'})
    with pytest.raises(ValueError,match='outside this isolated practice'):
        free.api('POST','/services/old-production-service/suspend')
    with pytest.raises(ValueError,match='Paid plan changes'):
        free.api('PATCH','/services/owned-new',{'serviceDetails':{'plan':'standard'}})


def test_private_token_must_be_single_line(tmp_path,monkeypatch):
    monkeypatch.setattr(free,'RUNTIME',tmp_path)
    (tmp_path/'api-token.txt').write_text('invalid\nsecond-line')
    with pytest.raises(ValueError,match='without whitespace'):
        free.api('GET','/owners')
