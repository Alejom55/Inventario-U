import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Pure policy and HTTP tests do not touch PostgreSQL."""
