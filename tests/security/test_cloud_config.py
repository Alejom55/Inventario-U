from pathlib import Path
import yaml


def test_e1_cloud_lab_cannot_shadow_shared_api_or_publish_private_ports():
    root=Path(__file__).parents[2]
    config=yaml.safe_load((root/'deploy/security/compose.aws.yml').read_text())
    services=config['services']
    assert set(services)=={'e1-api','e1-db','e1-prometheus'}
    assert all('ports' not in value for value in services.values())
    api=services['e1-api']
    assert '${SECURITY_API_IMAGE:' in api['image']
    assert 'e1-db:5432/security_e1' in api['environment']['DATABASE_URL']
    assert all('private' not in mount for mount in api['volumes'])
    assert 'shared_gateway' not in services['e1-db'].get('networks',[])
    gateway=(root/'deploy/security/Caddyfile.aws').read_text()
    assert 'reverse_proxy e1-api:8000' in gateway
    assert 'reverse_proxy api:8000' not in gateway
    assert '/api/v1/admin' not in gateway and '/api/v2/admin/resource-' not in gateway
