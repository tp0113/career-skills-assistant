import pytest

from app.cli import main
from evals.stub_llm import StubLLM


def test_cli_with_stub_prints_tool_events_reply_and_json(capsys):
    code = main(["--stub", "--employee", "E01", "What skills should I develop for my next career opportunity?"])
    out = capsys.readouterr().out
    assert code == 0
    assert "[tool] get_employee_profile" in out and "[tool] search_jobs" in out
    assert "Skills to develop" in out and '"skills"' in out and "4 model calls" in out


def test_cli_refusal_makes_no_model_call(capsys, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("the model was called for a refused message")

    monkeypatch.setattr(StubLLM, "chat", fail)  # any model call fails the test, not just the printed count
    main(["--stub", "--employee", "E01", "What are Marcus's skills?"])
    assert "0 model calls" in capsys.readouterr().out
