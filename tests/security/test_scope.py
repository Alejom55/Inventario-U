from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path

import pytest

from security.scope import validate_scope,scope_digest


@pytest.fixture
def accepted_unit_scope(tmp_path):
    # Contract-test fixture only. Never exported as a real group acceptance.
    example=Path(__file__).parents[2]/'security/rules-of-engagement.example.json'
    rules=json.loads(example.read_text());now=datetime.now(timezone.utc)
    rules.update(window_start_utc=(now-timedelta(minutes=1)).isoformat(),
        window_end_utc=(now+timedelta(minutes=10)).isoformat(),api_origin='https://example.invalid',
        prometheus_origin='https://example.invalid/prometheus',application_revision='a'*40,
        account_id='123456789012',instance_id='i-0123456789abcdef0')
    digest=scope_digest(rules)
    pdf=tmp_path/'unit-acceptance.pdf';pdf.write_bytes(b'%PDF-unit-fixture-not-a-real-signature')
    rules['participants']=[{'name':'Unit signer '+str(i),'accepted':True,'accepted_at_utc':(now-timedelta(minutes=2)).isoformat(),
        'signed_pdf':pdf.name,'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'accepted_scope_sha256':digest} for i in range(3)]
    path=tmp_path/'scope.json';path.write_text(json.dumps(rules))
    return path,rules,now


def test_accepted_contract_is_structurally_valid_but_not_a_real_signature_verifier(accepted_unit_scope):
    path,_,now=accepted_unit_scope
    assert validate_scope(path,now)['experiment']=='E1'


@pytest.mark.parametrize('change',[
    {'participants':[]}, {'synthetic_only':False}, {'account_id':''},
    {'api_origin':'http://example.invalid'}, {'maximum_requests':1000},
])
def test_missing_acceptance_or_scope_expansion_blocks_execution(accepted_unit_scope,change):
    path,rules,now=accepted_unit_scope;rules.update(change);path.write_text(json.dumps(rules))
    with pytest.raises(ValueError):validate_scope(path,now)


def test_changed_window_requires_a_new_personal_acceptance(accepted_unit_scope):
    path,rules,now=accepted_unit_scope
    rules['window_end_utc']=(now+timedelta(hours=2)).isoformat();path.write_text(json.dumps(rules))
    with pytest.raises(ValueError,match='scope or window changed'):validate_scope(path,now)


def test_altered_acceptance_pdf_is_rejected(accepted_unit_scope):
    path,_,now=accepted_unit_scope
    (path.parent/'unit-acceptance.pdf').write_bytes(b'%PDF-altered-unit-fixture')
    with pytest.raises(ValueError,match='digest changed'):validate_scope(path,now)
