from app.config import Settings


def test_cors_origins_parsed_from_comma_string(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    assert Settings().cors_origins == ["http://a.com", "http://b.com"]


def test_cors_origins_accepts_list():
    assert Settings(cors_origins=["http://x"]).cors_origins == ["http://x"]


def test_rerank_flag_from_env(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    assert Settings().rerank_enabled is True
