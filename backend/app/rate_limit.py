import hashlib
import hmac
import logging
import threading
import time
from dataclasses import dataclass

import boto3
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .security import TokenCodec, TokenError

logger = logging.getLogger(__name__)
COOKIE_NAME = "healthai_client"


@dataclass(frozen=True)
class Limit:
    requests: int
    window_seconds: int
    bucket: str


def limit_for(path: str, method: str) -> Limit | None:
    if method != "POST" or not path.startswith("/api/v1/"):
        return None
    if path == "/api/v1/voice/transcribe" or path == "/api/v1/images/pneumonia/predict":
        return Limit(8, 300, "media")
    if path.startswith("/api/v1/reports/") or "/predict" in path:
        return Limit(20, 300, "model")
    if path.startswith("/api/v1/triage/"):
        return Limit(30, 60, "chat")
    return Limit(30, 60, "api")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Signed-cookie fixed-window limiter with DynamoDB atomic counters.

    The cookie contains only an encrypted opaque identifier. DynamoDB receives
    only a SHA-256 hash and a short-lived counter, never chat or health content.
    """

    def __init__(self, app, *, secret: str, table_name: str | None, enabled: bool, secure_cookie: bool):
        super().__init__(app)
        self.enabled = enabled
        self.codec = TokenCodec(secret)
        self.secret = secret.encode("utf-8")
        self.table = boto3.resource("dynamodb").Table(table_name) if enabled and table_name else None
        self.secure_cookie = secure_cookie
        self._local: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit = limit_for(request.url.path, request.method)
        if not self.enabled or limit is None:
            return await call_next(request)

        client_id, issued = self._client_id(request)
        now = int(time.time())
        window = now // limit.window_seconds
        key_material = f"{client_id}:{limit.bucket}:{window}".encode()
        key = "rl#" + hashlib.sha256(key_material).hexdigest()
        count = self._increment(key, now + limit.window_seconds * 2)
        remaining = max(0, limit.requests - count)
        retry_after = limit.window_seconds - (now % limit.window_seconds)

        if count > limit.requests:
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": f"Too many requests. Please try again in {retry_after} seconds."},
                headers={"Retry-After": str(retry_after)},
            )
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(limit.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if issued:
            response.set_cookie(
                COOKIE_NAME,
                self.codec.encode({"kind": "client", "client_id": client_id}, ttl_seconds=60 * 60 * 24 * 180),
                max_age=60 * 60 * 24 * 180,
                httponly=True,
                secure=self.secure_cookie,
                samesite="lax",
                path="/",
            )
        return response

    def _client_id(self, request: Request) -> tuple[str, bool]:
        token = request.cookies.get(COOKIE_NAME)
        if token:
            try:
                value = str(self.codec.decode(token, "client")["client_id"])
                if len(value) == 64:
                    return value, False
            except (KeyError, TokenError):
                pass
        host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")[:256]
        opaque = hmac.new(self.secret, f"{host}|{user_agent}".encode(), hashlib.sha256).hexdigest()
        return opaque, True

    def _increment(self, key: str, expires_at: int) -> int:
        if self.table is not None:
            try:
                result = self.table.update_item(
                    Key={"pk": key},
                    UpdateExpression="SET expires_at = if_not_exists(expires_at, :expires) ADD request_count :one",
                    ExpressionAttributeValues={":expires": expires_at, ":one": 1},
                    ReturnValues="UPDATED_NEW",
                )
                return int(result["Attributes"]["request_count"])
            except Exception:
                logger.exception("DynamoDB rate-limit counter failed; using process-local fallback")
        now = int(time.time())
        with self._lock:
            count, expiry = self._local.get(key, (0, expires_at))
            if expiry <= now:
                count, expiry = 0, expires_at
            count += 1
            self._local[key] = (count, expiry)
            return count
