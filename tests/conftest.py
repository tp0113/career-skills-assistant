"""Shared test setup.

Test modules call load_settings() when they are imported, so an INJECTION_DEFENSE=off left in the
shell would quietly run every test with the defense off (Codex checkpoint 2 finding 6). Pytest
imports this file first, so the default is pinned here; tests that need it off say so with replace().
"""
import os

os.environ["INJECTION_DEFENSE"] = "on"
# The embedding router needs Ollama; tests that want it build their own with a fake embedder.
os.environ["EMBED_ROUTER"] = "off"
