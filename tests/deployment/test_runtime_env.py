import json
from unittest.mock import Mock

import pytest

from deploy import runtime_env


CONFIG = {
    "OCI_REGION": "sa-bogota-1", "OCI_NAMESPACE": "example",
    "OCI_BUCKET_NAME": "test-json", "DEPORTBACK_API_URL": "https://example.org",
}
SHA = "a" * 40


def test_secrets_and_urls_are_rendered_without_extra_metadata():
    text = runtime_env.render({**CONFIG, "DATABASE_SECRET_ID": "private-id"}, "p" * 32, "k" * 40, SHA)
    assert "DATABASE_SECRET_ID" not in text
    result = {name: json.loads(value) for name, value in (line.split("=", 1) for line in text.splitlines())}
    assert result["POSTGRES_PASSWORD"] == "p" * 32
    assert result["FASTIFY_API_URL"] == ""
    assert result["APP_REVISION"] == SHA


@pytest.mark.parametrize("config", [
    {**CONFIG, "OCI_NAMESPACE": "example\nEVIL=value"},
    {**CONFIG, "OCI_NAMESPACE": None},
    {**CONFIG, "DEPORTBACK_API_URL": "http://example.org"},
    {**CONFIG, "DEPORTBACK_API_URL": "https://user:secret@example.org"},
])
def test_rejects_unsafe_config(config):
    with pytest.raises(ValueError):
        runtime_env.render(config, "p" * 32, "k" * 40, SHA)


@pytest.mark.parametrize("password,key,sha", [
    ("short", "k" * 40, SHA), ("p" * 32, "short", SHA),
    ("p" * 32, "k" * 40, "main; touch /tmp/injected"),
])
def test_rejects_unsafe_credentials_or_revision(password, key, sha):
    with pytest.raises(ValueError):
        runtime_env.render(CONFIG, password, key, sha)


def test_dollars_are_escaped_for_compose():
    text = runtime_env.render({**CONFIG, "DEPORTBACK_API_URL": "https://example.org/$route"}, "p" * 32, "k" * 40, SHA)
    assert "$$route" in text


def test_reads_vault_and_writes_atomic_file(monkeypatch, tmp_path):
    import base64
    import io

    metadata = {"inventory_config": json.dumps({**CONFIG, "DATABASE_SECRET_ID": "db", "TEAM_SECRET_ID": "team"})}
    monkeypatch.setattr(runtime_env, "urlopen", lambda *a, **kw: io.BytesIO(json.dumps(metadata).encode()))
    monkeypatch.setattr(runtime_env.oci.auth.signers, "InstancePrincipalsSecurityTokenSigner", Mock())
    client = Mock()
    client.get_secret_bundle.side_effect = [
        Mock(data=Mock(secret_bundle_content=Mock(content=base64.b64encode(value.encode()).decode())))
        for value in ("p" * 32, "k" * 40)
    ]
    monkeypatch.setattr(runtime_env.oci.secrets, "SecretsClient", Mock(return_value=client))
    target = tmp_path / "runtime.env"
    runtime_env.main(SHA, str(target))
    assert target.read_text().startswith("APP_REVISION=")
    assert not target.with_suffix(".tmp").exists()
    assert client.get_secret_bundle.call_count == 2
