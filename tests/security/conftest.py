import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Identity and scope checks use synthetic routes, never business databases."""
