from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.rate_limit import COOKIE_NAME, RateLimitMiddleware, limit_for


def test_route_limits_separate_chat_and_heavy_media():
    chat = limit_for("/api/v1/triage/start", "POST")
    media = limit_for("/api/v1/voice/transcribe", "POST")

    assert chat and (chat.requests, chat.window_seconds, chat.bucket) == (30, 60, "chat")
    assert media and (media.requests, media.window_seconds, media.bucket) == (8, 300, "media")
    assert limit_for("/health", "GET") is None


def test_signed_client_cookie_is_issued_and_limit_returns_429(monkeypatch):
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        secret="test-secret-with-enough-entropy",
        table_name=None,
        enabled=True,
        secure_cookie=False,
    )

    @app.post("/api/v1/triage/start")
    def endpoint():
        return {"ok": True}

    monkeypatch.setattr(
        "backend.app.rate_limit.limit_for",
        lambda _path, _method: type("TinyLimit", (), {"requests": 2, "window_seconds": 60, "bucket": "test"})(),
    )
    client = TestClient(app)

    assert client.post("/api/v1/triage/start").status_code == 200
    assert COOKIE_NAME in client.cookies
    assert client.post("/api/v1/triage/start").status_code == 200
    limited = client.post("/api/v1/triage/start")
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert limited.json()["detail"].startswith("Too many requests")
