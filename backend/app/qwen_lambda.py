import json
import os
from pathlib import Path
from typing import Any

from .qwen_runtime import DECISION_JSON_SCHEMA

MODEL_PATH = Path(os.environ.get("HEALTHAI_QWEN_MODEL_PATH", "/opt/qwen/Qwen3-0.6B-Q8_0.gguf"))
_model = None


def _get_model():
    global _model
    if _model is None:
        from llama_cpp import Llama

        _model = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=4096,
            n_batch=256,
            n_threads=max(1, int(os.environ.get("HEALTHAI_QWEN_THREADS", "2"))),
            verbose=False,
        )
    return _model


def _complete(system: str, user: str, schema: dict[str, Any], max_tokens: int) -> str:
    response = _get_model().create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        top_p=0.9,
        max_tokens=max_tokens,
        response_format={"type": "json_object", "schema": schema},
    )
    content = response["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Qwen produced an empty response.")
    return content.strip()


def handler(event, _context):
    try:
        operation = event.get("operation")
        if operation == "decision":
            content = _complete(
                (
                    "You are the private HealthAI conversation router. Follow the supplied policy exactly. "
                    "Do not request identity or contact data. Return one JSON object only. /no_think"
                ),
                str(event["prompt"]),
                DECISION_JSON_SCHEMA,
                220,
            )
            return {"content": content}
        if operation == "select_symptom_question":
            candidates = event.get("candidates", {})
            if not isinstance(candidates, dict) or not candidates:
                raise ValueError("Approved candidates are required.")
            schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {"question_id": {"type": "string", "enum": list(candidates)}},
                "required": ["question_id"],
            }
            candidate_text = "\n".join(f"{key}: {value}" for key, value in candidates.items())
            raw = _complete(
                "Select one approved follow-up question ID. Do not answer the medical question. Return JSON only. /no_think",
                (
                    f"User messages: {json.dumps(event.get('messages', []), ensure_ascii=False)}\n"
                    f"Approved candidates:\n{candidate_text}\nChoose the most useful unanswered question."
                ),
                schema,
                30,
            )
            return {"question_id": json.loads(raw)["question_id"]}
        raise ValueError("Unsupported Qwen operation.")
    except Exception as exc:
        return {"error": type(exc).__name__}
