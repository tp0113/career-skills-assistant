"""Every tunable value, read once from the environment (.env is loaded if present).

This module imports nothing from the app, so every other module can import it.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    ollama_url: str
    ollama_model: str
    # Sent on every Ollama request. The 32K default spills to CPU on an 8 GB GPU.
    ollama_num_ctx: int
    anthropic_model: str
    data_dir: Path
    enrollments_path: Path
    request_log_path: Path
    injection_defense: bool


def _path(name: str, default: str) -> Path:
    """Relative paths are resolved from the repo root, so commands work from any folder."""
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else ROOT / value


def load_settings() -> Settings:
    return Settings(
        llm_provider=os.getenv("LLM_PROVIDER", "ollama").lower(),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        ollama_num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        data_dir=_path("DATA_DIR", "data"),
        enrollments_path=_path("ENROLLMENTS_PATH", "var/enrollments.json"),
        request_log_path=_path("REQUEST_LOG_PATH", "logs/requests.jsonl"),
        injection_defense=os.getenv("INJECTION_DEFENSE", "on").lower() != "off",
    )
