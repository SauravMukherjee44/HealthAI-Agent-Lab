import time

import pytest

from backend.app.security import TokenCodec, TokenError


def test_token_round_trip_and_purpose_binding():
    codec = TokenCodec("test-secret")
    token = codec.encode({"kind": "triage", "value": 42})
    assert codec.decode(token, "triage")["value"] == 42
    with pytest.raises(TokenError):
        codec.decode(token, "report")


def test_token_tampering_is_rejected():
    codec = TokenCodec("test-secret")
    token = codec.encode({"kind": "triage"})
    with pytest.raises(TokenError):
        codec.decode(token[:-2] + "aa", "triage")


def test_expired_token_is_rejected(monkeypatch):
    codec = TokenCodec("test-secret")
    token = codec.encode({"kind": "triage"}, ttl_seconds=1)
    monkeypatch.setattr(time, "time", lambda: 10_000_000_000)
    with pytest.raises(TokenError):
        codec.decode(token, "triage")
