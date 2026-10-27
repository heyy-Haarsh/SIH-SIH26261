"""Phase 3: LLM extractor providers and none-mode."""

from app.document_processing.llm_extractor import (
    GeminiLLMExtractor,
    NullLLMExtractor,
    OpenAILLMExtractor,
    get_llm_extractor,
)


def test_provider_none_returns_empty(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    from app.core.config import get_settings

    get_settings.cache_clear()
    # Re-bind settings singleton used by module
    import app.core.config as cfg

    cfg.settings = cfg.get_settings()
    ext = get_llm_extractor("none")
    assert isinstance(ext, NullLLMExtractor)
    assert ext.extract("Institution Name: X", {"properties": {"institution_name": {}}}) == {}


def test_gemini_without_key_degrades(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings
    import app.core.config as cfg

    get_settings.cache_clear()
    cfg.settings = cfg.get_settings()
    out = GeminiLLMExtractor().extract("text", {"properties": {"a": {}}})
    assert out == {}


def test_openai_without_key_degrades(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import get_settings
    import app.core.config as cfg

    get_settings.cache_clear()
    cfg.settings = cfg.get_settings()
    out = OpenAILLMExtractor().extract("text", {"properties": {"a": {}}})
    assert out == {}


def test_llm_never_returns_pass_fail_decision():
    """Extractor returns field dict only — no pass/fail keys."""
    result = NullLLMExtractor().extract("x", {"properties": {}})
    assert "pass" not in result
    assert "fail" not in result
    assert "decision" not in result
