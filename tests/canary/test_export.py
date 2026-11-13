import json
from unittest.mock import Mock

import pytest

from deploy.canary import export


VALUES = {"APP_REVISION": "a" * 40, "OCI_REGION": "test", "OCI_NAMESPACE": "namespace",
          "OCI_BUCKET_NAME": "private", "TEAM_API_KEY": "secret-api-key",
          "GRAFANA_PASSWORD": "secret-grafana", "POSTGRES_PASSWORD": "secret-database"}


def test_evidence_uses_private_sdk_destination_without_credentials(monkeypatch):
    monkeypatch.setattr(export, "load_env", lambda path: VALUES)
    monkeypatch.setattr(export, "collect", lambda values, action: {"result": "rollback verified"})
    monkeypatch.setattr(export.oci.auth.signers, "InstancePrincipalsSecurityTokenSigner", Mock())
    sdk = Mock()
    monkeypatch.setattr(export.oci.object_storage, "ObjectStorageClient", Mock(return_value=sdk))
    export.main("regression")
    args = sdk.put_object.call_args.args
    assert args[:3] == ("namespace", "private", "canary-evidence/" + "a" * 40 + "/regression.json")
    assert json.loads(args[3]) == {"result": "rollback verified"}


def test_evidence_rejects_a_report_containing_any_credential(monkeypatch):
    monkeypatch.setattr(export, "load_env", lambda path: VALUES)
    monkeypatch.setattr(export, "collect", lambda values, action: {"accidental": values["TEAM_API_KEY"]})
    with pytest.raises(RuntimeError, match="credentials"):
        export.main("install")


def test_operator_access_is_separate_from_public_evidence_and_logs(monkeypatch, capsys):
    monkeypatch.setattr(export, "load_env", lambda path: VALUES)
    monkeypatch.setattr(export, "collect", lambda values, action: {"result": "installed"})
    monkeypatch.setattr(export.oci.auth.signers, "InstancePrincipalsSecurityTokenSigner", Mock())
    sdk = Mock()
    monkeypatch.setattr(export.oci.object_storage, "ObjectStorageClient", Mock(return_value=sdk))
    export.main("install")
    private, evidence = sdk.put_object.call_args_list
    assert private.args[2].startswith("canary-operator-access/")
    assert json.loads(private.args[3]) == {"user": "admin", "password": VALUES["GRAFANA_PASSWORD"]}
    assert VALUES["GRAFANA_PASSWORD"].encode() not in evidence.args[3]
    assert VALUES["TEAM_API_KEY"].encode() not in private.args[3]
    assert VALUES["GRAFANA_PASSWORD"] not in capsys.readouterr().out
