import hashlib
import json

import jwt

from security.identity_tokens import create_keypair
from security.prepare import refresh_honeytoken


def test_refresh_decoy_preserves_issuer_and_other_secrets(tmp_path):
    private,public=create_keypair(tmp_path)
    original=private.read_bytes()
    values={'issuer_private_key':str(private),'legacy_key':'unchanged','honey_token':'old'}
    (tmp_path/'credentials.json').write_text(json.dumps(values))
    for current in ('R0','R1'):
        (tmp_path/(current+'.env')).write_text('TEAM_API_KEY=unchanged\nSECURITY_HONEYTOKEN_SHA256=old\n')
    refresh_honeytoken(tmp_path)
    actual=json.loads((tmp_path/'credentials.json').read_text())
    assert actual['legacy_key']=='unchanged' and private.read_bytes()==original
    claims=jwt.decode(actual['honey_token'],public.read_bytes(),algorithms=['EdDSA'],audience='inventario-u')
    assert claims['sub']=='unused-decoy-agent' and claims['exp']-claims['iat']==300
    for current in ('R0','R1'):
        assert hashlib.sha256(actual['honey_token'].encode()).hexdigest() in (tmp_path/(current+'.env')).read_text()
