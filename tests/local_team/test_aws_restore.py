import json

import pytest

from deploy.aws.restore_credentials import previous_credentials


def test_restore_selects_only_existing_service_secrets(tmp_path):
    path=tmp_path/'private.json'
    path.write_text(json.dumps({'TEAM_API_KEY':'a'*64,'RESOURCE_ADMIN_KEY':'b'*64,'METRICS_BEARER_TOKEN':'c'*64,
        'POSTGRES_PASSWORD':'must-not-replace-the-new-database-password','APP_REVISION':'d'*40}))
    assert set(previous_credentials(path))=={'TEAM_API_KEY','RESOURCE_ADMIN_KEY','METRICS_BEARER_TOKEN'}


def test_restore_rejects_incomplete_credentials_without_printing_them(tmp_path):
    path=tmp_path/'private.json';path.write_text(json.dumps({'TEAM_API_KEY':'short-sensitive-value'}))
    with pytest.raises(ValueError) as error:previous_credentials(path)
    assert 'short-sensitive-value' not in str(error.value)
