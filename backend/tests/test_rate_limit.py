from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.rate_limit import COOKIE_NAME, Limit, LimitPolicy, RateLimitMiddleware, limit_for, limits_for


def test_route_limits_separate_chat_and_heavy_media():
    chat = limit_for("/api/v1/triage/start", "POST")
    media = limit_for("/api/v1/voice/transcribe", "POST")

    assert chat and (chat.requests, chat.window_seconds, chat.bucket) == (20, 60, "chat-short")
    assert media and (media.requests, media.window_seconds, media.bucket) == (4, 600, "voice-short")
    assert limit_for("/health", "GET") is None

    warm = limits_for("/api/v1/runtime/warm", "POST")
    assert warm
    assert warm.client[0].requests == 6
    assert warm.ip[0].requests == 60
    assert warm.global_[0].requests == 300

    chat_policy = limits_for("/api/v1/triage/message", "POST")
    assert chat_policy
    assert chat_policy.client[1].requests == 200
    assert chat_policy.ip[0].requests == 60
    assert chat_policy.global_[0].requests == 1000


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
        "backend.app.rate_limit.limits_for",
        lambda _path, _method: LimitPolicy(
            client=(Limit(2, 60, "test-client"),),
            ip=(Limit(10, 60, "test-ip"),),
            global_=(Limit(100, 60, "test-global"),),
        ),
    )
    client = TestClient(app)

    assert client.post("/api/v1/triage/start").status_code == 200
    assert COOKIE_NAME in client.cookies
    assert client.post("/api/v1/triage/start").status_code == 200
    limited = client.post("/api/v1/triage/start")
    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert limited.json()["detail"].startswith("Too many requests")


def test_cookie_deletion_and_user_agent_rotation_do_not_bypass_ip_limit(monkeypatch):
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
        "backend.app.rate_limit.limits_for",
        lambda _path, _method: LimitPolicy(
            client=(Limit(10, 60, "client"),),
            ip=(Limit(2, 60, "ip"),),
            global_=(Limit(100, 60, "global"),),
        ),
    )
    client = TestClient(app)
    for user_agent in ("browser-one", "browser-two"):
        client.cookies.clear()
        assert client.post("/api/v1/triage/start", headers={"user-agent": user_agent}).status_code == 200

    client.cookies.clear()
    limited = client.post("/api/v1/triage/start", headers={"user-agent": "browser-three"})
    assert limited.status_code == 429


def test_global_capacity_cap_applies_across_anonymous_identities(monkeypatch):
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
        "backend.app.rate_limit.limits_for",
        lambda _path, _method: LimitPolicy(
            client=(Limit(100, 60, "client"),),
            ip=(Limit(100, 60, "ip"),),
            global_=(Limit(2, 60, "global"),),
        ),
    )
    client = TestClient(app)
    assert client.post("/api/v1/triage/start").status_code == 200
    assert client.post("/api/v1/triage/start").status_code == 200
    limited = client.post("/api/v1/triage/start")
    assert limited.status_code == 429
    assert limited.json()["detail"].startswith("The research service")
