import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def mock_cache_and_redis(settings, monkeypatch):
    """
    Substitui o Redis por cache em memória para que os testes do DRF (Rate Limiting)
    funcionem sem precisar de um servidor Redis rodando na máquina.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-test-cache",
        }
    }

    # Mocka a conexão direta do django_redis usada pelos locks do cinema
    mock_redis = MagicMock()
    mock_redis.exists.return_value = False
    mock_redis.mget.return_value = []
    
    # Substitui a função `get_redis_connection` importada dentro dos serviços e views
    monkeypatch.setattr("cinema.services.reservation.get_redis_connection", lambda alias="default": mock_redis)
    try:
        monkeypatch.setattr("cinema.views.get_redis_connection", lambda alias="default": mock_redis)
    except AttributeError:
        pass
