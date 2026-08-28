import base64
import hashlib
import json
import os
import time
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenError(ValueError):
    pass


class TokenCodec:
    def __init__(self, secret: str):
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()
        self._cipher = AESGCM(self._key)

    def encode(self, payload: dict[str, Any], ttl_seconds: int = 1800) -> str:
        protected = {**payload, "expires_at": int(time.time()) + ttl_seconds}
        nonce = os.urandom(12)
        encrypted = self._cipher.encrypt(
            nonce,
            json.dumps(protected, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
            None,
        )
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii").rstrip("=")

    def decode(self, token: str, expected_kind: str) -> dict[str, Any]:
        try:
            padded = token + "=" * (-len(token) % 4)
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            payload = json.loads(self._cipher.decrypt(raw[:12], raw[12:], None))
        except Exception as exc:
            raise TokenError("The session token is invalid or has been altered.") from exc
        if payload.get("kind") != expected_kind:
            raise TokenError("The session token has the wrong purpose.")
        if int(payload.get("expires_at", 0)) < int(time.time()):
            raise TokenError("The session has expired. Start a new assessment.")
        return payload
