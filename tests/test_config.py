from app.config import ROOT, load_settings


def test_defaults_are_local_and_safe(monkeypatch):
    for name in ("LLM_PROVIDER", "OLLAMA_NUM_CTX", "INJECTION_DEFENSE", "ENROLLMENTS_PATH"):
        monkeypatch.delenv(name, raising=False)
    s = load_settings()
    assert s.llm_provider == "ollama"
    assert s.ollama_num_ctx == 8192
    assert s.injection_defense is True
    assert s.enrollments_path == ROOT / "var" / "enrollments.json"


def test_defense_can_be_turned_off_only_explicitly(monkeypatch):
    monkeypatch.setenv("INJECTION_DEFENSE", "OFF")
    assert load_settings().injection_defense is False
    monkeypatch.setenv("INJECTION_DEFENSE", "no")
    assert load_settings().injection_defense is True
