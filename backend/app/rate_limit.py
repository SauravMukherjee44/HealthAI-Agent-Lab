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


@dataclass(frozen=True)
class LimitPolicy:
    client: tuple[Limit, ...]
    ip: tuple[Limit, ...]
    global_: tuple[Limit, ...]


DAY = 60 * 60 * 24


def limits_for(path: str, method: str) -> LimitPolicy | None:
    if method != "POST" or not path.startswith("/api/v1/"):
        return None
    if path == "/api/v1/voice/transcribe":
        return LimitPolicy(
            client=(Limit(4, 600, "voice-short"), Limit(20, DAY, "voice-daily")),
            ip=(Limit(12, 600, "voice-ip-short"), Limit(60, DAY, "voice-ip-daily")),
            global_=(Limit(100, DAY, "voice-capacity"),),
        )
    if path == "/api/v1/images/pneumonia/predict":
        return LimitPolicy(
            client=(Limit(10, 600, "image-short"), Limit(50, DAY, "image-daily")),
            ip=(Limit(30, 600, "image-ip-short"), Limit(150, DAY, "image-ip-daily")),
            global_=(Limit(300, DAY, "image-capacity"),),
        )
    if path.startswith("/api/v1/reports/"):
        return LimitPolicy(
            client=(Limit(10, 600, "report-short"), Limit(50, DAY, "report-daily")),
            ip=(Limit(30, 600, "report-ip-short"), Limit(150, DAY, "report-ip-daily")),
            global_=(Limit(500, DAY, "report-capacity"),),
        )
    if "/predict" in path:
        return LimitPolicy(
            client=(Limit(20, 300, "model-short"), Limit(200, DAY, "model-daily")),
            ip=(Limit(60, 300, "model-ip-short"), Limit(600, DAY, "model-ip-daily")),
            global_=(Limit(2000, DAY, "model-capacity"),),
        )
    if path.startswith("/api/v1/triage/"):
        return LimitPolicy(
            client=(Limit(20, 60, "chat-short"), Limit(200, DAY, "chat-daily")),
            ip=(Limit(60, 60, "chat-ip-short"), Limit(500, DAY, "chat-ip-daily")),
            global_=(Limit(1000, DAY, "chat-capacity"),),
        )
    return LimitPolicy(
        client=(Limit(30, 60, "api-short"), Limit(300, DAY, "api-daily")),
        ip=(Limit(90, 60, "api-ip-short"), Limit(900, DAY, "api-ip-daily")),
        global_=(Limit(3000, DAY, "api-capacity"),),
    )


def limit_for(path: str, method: str) -> Limit | None:
    """Return the primary browser limit for compatibility and UI metadata."""
    policy = limits_for(path, method)
    return policy.client[0] if policy else None


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
        policy = limits_for(request.url.path, request.method)
        if not self.enabled or policy is None:
            return await call_next(request)

        client_id, issued = self._client_id(request)
        ip_id = self._ip_id(request)
        now = int(time.time())
        checks = (
            *(("client", client_id, limit) for limit in policy.client),
            *(("ip", ip_id, limit) for limit in policy.ip),
            *(("global", "healthai", limit) for limit in policy.global_),
        )
        violations: list[tuple[str, Limit, int]] = []
        primary_count = 0
        for index, (scope, identity, limit) in enumerate(checks):
            window = now // limit.window_seconds
            key_material = f"{scope}:{identity}:{limit.bucket}:{limit.window_seconds}:{window}".encode()
            key = "rl#" + hashlib.sha256(key_material).hexdigest()
            count = self._increment(key, now + limit.window_seconds * 2)
            if index == 0:
                primary_count = count
            if count > limit.requests:
                violations.append((scope, limit, limit.window_seconds - (now % limit.window_seconds)))

        primary = policy.client[0]
        remaining = max(0, primary.requests - primary_count)
        if violations:
            scope, _violated_limit, retry_after = max(violations, key=lambda item: item[2])
            detail = (
                "The research service has reached its shared capacity. Please try again later."
                if scope == "global"
                else f"Too many requests. Please try again in {retry_after} seconds."
            )
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": detail},
                headers={"Retry-After": str(retry_after)},
            )
        else:
            response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(primary.requests)
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

    def _ip_id(self, request: Request) -> str:
        # request.client is populated from API Gateway's authenticated sourceIp
        # by Mangum. Do not trust a caller-provided X-Forwarded-For value here.
        host = request.client.host if request.client else "unknown"
        return hmac.new(self.secret, f"ip|{host}".encode(), hashlib.sha256).hexdigest()

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
