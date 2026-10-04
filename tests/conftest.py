"""Gemeinsame Testumgebung.

- Streamlit-Secrets und Sitzungsstatus werden durch isolierte Testobjekte ersetzt,
  bevor die App-Module importiert werden. Echte Schlüssel werden nie gelesen.
- Jeder Netzwerkzugriff schlägt fehl, solange ein Test ihn nicht ausdrücklich ersetzt.
- Jeder Test erhält eine eigene, leere SQLite-Datenbank.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

TEST_SECRETS = {"openai_api_key": "test-openai-key", "vercel_token": "test-vercel-token"}


class SessionState(dict):
    """Nachbildung von st.session_state mit Attribut- und Schlüsselzugriff."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]


# Originale für die Oberflächentests (AppTest braucht den echten Sitzungsstatus).
REAL_SESSION_STATE = st.session_state
REAL_SECRETS = st.secrets
st.secrets = dict(TEST_SECRETS)
st.session_state = SessionState()

import logic  # noqa: E402


class FakeResponse:
    """Minimale requests.Response-Nachbildung für Netzwerktests."""

    def __init__(self, status_code=200, payload=None, text=None, url="https://example.test/"):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else (json.dumps(payload) if payload is not None else "")
        self.url = url

    def json(self):
        if self._payload is None:
            raise ValueError("Keine JSON-Antwort")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeUpload:
    """Nachbildung einer Streamlit-UploadedFile."""

    def __init__(self, name: str, data: bytes, mime_type: str = ""):
        self.name = name
        self._data = data
        self.type = mime_type

    def getvalue(self) -> bytes:
        return self._data


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """Verhindert versehentliche echte HTTP-Aufrufe in allen Tests."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("Unerwarteter Netzwerkzugriff im Test")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


@pytest.fixture(autouse=True)
def session(monkeypatch):
    """Frischer Sitzungsstatus mit den Standardwerten der App."""
    state = SessionState()
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "query_params", {})
    logic.initialize_session_state()
    state.user_id = 1
    state.user_email = "kunde@example.com"
    state.analytics_site_id = "11111111-2222-4333-8444-555555555555"
    return state


@pytest.fixture(autouse=True)
def database(monkeypatch, tmp_path):
    """Leere, isolierte Datenbank je Test."""
    monkeypatch.setattr(logic, "DATABASE_PATH", tmp_path / "test.db")
    logic.initialize_database()
    return tmp_path / "test.db"


@pytest.fixture
def user_id():
    logic.register_user("kunde@example.com", "sicheres-passwort")
    return logic.authenticate_user("kunde@example.com", "sicheres-passwort")[0]


@pytest.fixture
def fake_openai(monkeypatch):
    """Ersetzt den OpenAI-Client; Antworten werden pro Test festgelegt."""
    calls = []
    replies = {"chat": "<!doctype html><html><head></head><body><h1>KI</h1></body></html>", "error": None}

    def create(**kwargs):
        calls.append(kwargs)
        if replies["error"]:
            raise replies["error"]
        message = SimpleNamespace(content=replies["chat"])
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        embeddings=SimpleNamespace(create=None),
    )
    monkeypatch.setattr(logic, "client", client)
    return SimpleNamespace(client=client, calls=calls, replies=replies)


@pytest.fixture
def js():
    """Prüft erzeugtes JavaScript mit der V8-Engine auf gültige Syntax."""
    from py_mini_racer import MiniRacer

    engine = MiniRacer()

    def assert_valid(code: str) -> None:
        body = code.replace("export default ", "", 1)
        engine.eval(f"new Function({json.dumps(body)})")

    return assert_valid


@pytest.fixture
def scripts():
    """Extrahiert alle Inline-Skripte aus einem HTML-Dokument."""
    import re

    def extract(html: str) -> list[str]:
        return re.findall(r"<script\b[^>]*>(.*?)</script>", html, flags=re.S | re.I)

    return extract


SIMPLE_HTML = (
    '<!doctype html><html lang="de"><head><title>Test</title></head>'
    "<body><main><h1>Willkommen</h1><img src=\"alt.png\" alt=\"Alt\"></main></body></html>"
)
