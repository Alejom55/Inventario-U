import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Circuit and experiment tests do not access a database."""


@pytest.fixture(autouse=True)
def reset_breakers(monkeypatch):
    from app.integrations import resilience
    monkeypatch.setenv("RESILIENCE_MODE", "baseline")
    monkeypatch.setattr(resilience, "_breakers", {})
