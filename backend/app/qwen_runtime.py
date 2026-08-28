import json
from dataclasses import dataclass
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class QwenRuntimeUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class QwenRuntimeStatus:
    available: bool
    backend: str
    model: str
    detail: str


class DockerModelRunner:
    """Minimal OpenAI-compatible client for the local Docker Model Runner."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def status(self) -> QwenRuntimeStatus:
        try:
            payload = self._request("GET", "/models", timeout_seconds=2.0)
        except QwenRuntimeUnavailable as exc:
            return QwenRuntimeStatus(False, "docker-model-runner", self.model, str(exc))
        models = [item.get("id", "").lower() for item in payload.get("data", [])]
        requested = self.model.lower()
        available = requested in models or any(requested.endswith(item) or item.endswith(requested) for item in models)
        return QwenRuntimeStatus(
            available,
            "docker-model-runner",
            self.model,
            "model-ready" if available else "runtime-ready-model-missing",
        )

    def warm(self) -> bool:
        """Probe the local model runner without generating or retaining content."""
        return self.status().available

    def __call__(self, prompt: str) -> str:
        payload = self._request(
            "POST",
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are the private HealthAI conversation router. Follow the supplied policy exactly. "
                            "Do not ask for a name, identity, contact detail, or account. "
                            "Return only one JSON object and do not include markdown or hidden reasoning. /no_think"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "top_p": 0.9,
                "max_tokens": 220,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "healthai_orchestration_decision",
                        "strict": True,
                        "schema": DECISION_JSON_SCHEMA,
                    },
                },
            },
        )
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenRuntimeUnavailable("The local Qwen response did not contain message content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise QwenRuntimeUnavailable("The local Qwen response was empty.")
        return content.strip()

    def select_symptom_question(self, messages: list[str], candidates: dict[str, str]) -> str:
        candidate_text = "\n".join(f"{key}: {value}" for key, value in candidates.items())
        payload = self._request(
            "POST",
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Select one approved follow-up question ID for a non-diagnostic symptom interview. "
                            "Do not answer the medical question. Return JSON only. /no_think"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"User messages: {json.dumps(messages[-4:], ensure_ascii=False)}\n"
                            f"Approved candidates:\n{candidate_text}\n"
                            "Choose the single most useful question not already answered."
                        ),
                    },
                ],
                "temperature": 0.0,
                "max_tokens": 30,
                "stream": False,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "symptom_question_selection",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "question_id": {
                                    "type": "string",
                                    "enum": list(candidates),
                                }
                            },
                            "required": ["question_id"],
                        },
                    },
                },
            },
            timeout_seconds=min(self.timeout_seconds, 12.0),
        )
        try:
            content = json.loads(payload["choices"][0]["message"]["content"])
            question_id = content["question_id"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise QwenRuntimeUnavailable("Qwen returned an invalid symptom-question selection.") from exc
        if question_id not in candidates:
            raise QwenRuntimeUnavailable("Qwen selected a question outside the approved set.")
        return question_id

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        timeout_seconds: float | None = None,
    ) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=timeout_seconds or self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise QwenRuntimeUnavailable(f"Local Qwen request failed ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise QwenRuntimeUnavailable(f"Local Qwen runtime unavailable: {exc}") from exc


class AwsLambdaModelRunner:
    """Synchronous client for the private scale-to-zero Qwen Lambda tool."""

    def __init__(self, function_name: str, model: str, client=None):
        if client is None:
            import boto3

            client = boto3.client("lambda")
        self.client = client
        self.function_name = function_name
        self.model = model

    def status(self) -> QwenRuntimeStatus:
        return QwenRuntimeStatus(True, "aws-lambda", self.model, "configured-private-function")

    def warm(self) -> bool:
        """Start model loading asynchronously so the browser never waits for it."""
        try:
            self.client.invoke(
                FunctionName=self.function_name,
                InvocationType="Event",
                Payload=json.dumps({"operation": "warmup"}).encode("utf-8"),
            )
        except Exception as exc:
            raise QwenRuntimeUnavailable("Private Qwen Lambda warm-up failed.") from exc
        return True

    def __call__(self, prompt: str) -> str:
        return self._invoke({"operation": "decision", "prompt": prompt})["content"]

    def select_symptom_question(self, messages: list[str], candidates: dict[str, str]) -> str:
        payload = self._invoke(
            {
                "operation": "select_symptom_question",
                "messages": messages[-6:],
                "candidates": candidates,
            }
        )
        question_id = payload.get("question_id")
        if question_id not in candidates:
            raise QwenRuntimeUnavailable("Qwen Lambda selected a question outside the approved set.")
        return question_id

    def _invoke(self, payload: dict) -> dict:
        try:
            response = self.client.invoke(
                FunctionName=self.function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode("utf-8"),
            )
            body = json.load(response.get("Payload", BytesIO(b"{}")))
        except Exception as exc:
            raise QwenRuntimeUnavailable("Private Qwen Lambda invocation failed.") from exc
        if response.get("FunctionError") or body.get("error"):
            raise QwenRuntimeUnavailable("Private Qwen Lambda returned an error.")
        return body


DECISION_JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {
            "type": "string",
            "enum": ["respond", "ask_question", "call_tool", "explain_result", "escalate", "unsupported"],
        },
        "tool": {
            "type": ["string", "null"],
            "enum": ["heart_risk", "diabetes_risk", "kidney_risk", "liver_risk", None],
        },
        "arguments": {"type": "object"},
        "known_fields": {"type": "object"},
        "field_evidence": {"type": "object", "additionalProperties": {"type": "string"}},
        "missing_fields": {"type": "array", "items": {"type": "string"}},
        "response": {"type": "string"},
        "mode": {
            "type": "string",
            "enum": ["conversation", "wellness", "symptom_interview", "screening"],
        },
    },
    "required": [
        "action",
        "tool",
        "arguments",
        "known_fields",
        "field_evidence",
        "missing_fields",
        "response",
        "mode",
    ],
}
