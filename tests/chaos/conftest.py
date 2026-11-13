import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Circuit and experiment tests do not access a database."""


@pytest.fixture(autouse=True)
def reset_breakers(monkeypatch):
    from app.integrations import resilience
    monkeypatch.setenv("RESILIENCE_MODE", "baseline")
    monkeypatch.setattr(resilience, "_breakers", {})


@pytest.fixture(autouse=True)
def isolated_lease(tmp_path, monkeypatch):
    from chaos_lab import providers
    monkeypatch.setattr(providers, "_fault_armed", False)
    monkeypatch.delenv("CHAOS_EVIDENCE_FILE", raising=False)
    monkeypatch.setenv("CHAOS_LEASE_DB", str(tmp_path / "leases.sqlite3"))
