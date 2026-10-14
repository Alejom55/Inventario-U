from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from deploy import smoke


def test_smoke_checks_database_storage_and_auth(monkeypatch):
    saved = {}

    def request(path, body=None, authenticated=True):
        if path == "/health":
            return {"status": "ok"}
        if not authenticated:
            raise HTTPError("", 401, "Unauthorized", {}, None)
        if path == "/skus":
            return []
        if path == "/storage":
            saved.update(body["data"])
            return {"status": "stored"}
        if path.startswith("/storage?"):
            return {"objects": ["smoke-object"]}
        return saved

    monkeypatch.setattr(smoke, "request", request)
    smoke.main()
    assert saved["source"] == "deployment-smoke"


def test_smoke_fails_when_api_is_open(monkeypatch):
    monkeypatch.setattr(smoke, "request", Mock(return_value={"status": "ok"}))
    with pytest.raises(AssertionError, match="authentication"):
        smoke.main()
