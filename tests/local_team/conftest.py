import pytest

@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Configuration checks do not connect to any database."""
