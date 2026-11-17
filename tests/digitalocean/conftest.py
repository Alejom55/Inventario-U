import pytest


@pytest.fixture(autouse=True)
def limpiar_base_de_pruebas():
    """Cost/deletion guard tests never access a database or cloud account."""
