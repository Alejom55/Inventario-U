from datetime import datetime,timezone,timedelta
import pytest
from deploy.security.aws_e1 import authorize_owner


def test_explicit_owner_command_creates_only_bounded_separate_lab_scope(tmp_path):
    now=datetime.now(timezone.utc)
    rules=authorize_owner(tmp_path/'owner.json',60,now)
    assert rules['participants']==[] and rules['authorization_mode']=='owner_isolated_lab'
    assert rules['owner_authorization']['source']=='owner_cli'
    assert rules['api_origin'].startswith('https://e1.')
    assert datetime.fromisoformat(rules['window_end_utc'])==now+timedelta(minutes=60)


@pytest.mark.parametrize('minutes',[0,4,121,1000])
def test_owner_window_cannot_be_unbounded(tmp_path,minutes):
    with pytest.raises(ValueError):authorize_owner(tmp_path/'owner.json',minutes)
    assert not (tmp_path/'owner.json').exists()
