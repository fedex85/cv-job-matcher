import pytest

from src.config import load_settings


def test_defaults_and_env_parsing(monkeypatch):
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("EMBEDDING_BACKEND", "tfidf   # comentario inline")
    s = load_settings()
    assert s.port == 9000 and s.cors_origins == ("http://a.test", "http://b.test")
    assert not s.llm_enabled and s.embedding_backend == "tfidf"


@pytest.mark.parametrize("var,value", [("PORT", "abc"), ("EMBEDDING_BACKEND", "magia"),
                                       ("WEIGHT_SKILLS", "-1")])
def test_invalid_config_fails_fast(monkeypatch, var, value):
    monkeypatch.setenv(var, value)
    with pytest.raises(ValueError):
        load_settings()


def test_production_requires_api_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("API_KEY", raising=False)
    with pytest.raises(ValueError):
        load_settings()


def test_secret_not_in_repr():
    from src.config import Settings
    assert "supersecreta" not in repr(Settings(groq_api_key="supersecreta"))
