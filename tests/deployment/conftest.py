import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Deployment tests use mocks; override the global PostgreSQL fixture."""
