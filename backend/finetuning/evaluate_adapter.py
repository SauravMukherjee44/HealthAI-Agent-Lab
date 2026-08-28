import argparse
import json
import time
from pathlib import Path

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "backend" / "evaluation" / "qwen_scenarios.jsonl"
TRAIN_DATA = ROOT / "backend" / "finetuning" / "data" / "train.jsonl"
REQUIRED_KEYS = {
    "action",
    "tool",
    "arguments",
    "known_fields",
    "field_evidence",
    "missing_fields",
    "response",
    "mode",
}
ALLOWED_ACTIONS = {
    "respond",
    "ask_question",
    "call_tool",
    "explain_result",
    "escalate",
    "unsupported",
}
ALLOWED_TOOLS = {None, "heart_risk", "diabetes_risk", "kidney_risk", "liver_risk"}
ALLOWED_MODES = {"conversation", "wellness", "symptom_interview", "screening"}


def _extract_json(text: str) -> dict:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No JSON object found in adapter output.")


def _contract_valid(decision: dict) -> bool:
    return (
        set(decision) == REQUIRED_KEYS
        and decision.get("action") in ALLOWED_ACTIONS
        and decision.get("tool") in ALLOWED_TOOLS
        and isinstance(decision.get("arguments"), dict)
        and isinstance(decision.get("known_fields"), dict)
        and isinstance(decision.get("field_evidence"), dict)
        and isinstance(decision.get("missing_fields"), list)
        and isinstance(decision.get("response"), str)
        and decision.get("mode") in ALLOWED_MODES
    )


def _evidence_valid(decision: dict, messages: list[str]) -> bool:
    known = decision.get("known_fields", {})
    evidence = decision.get("field_evidence", {})
    conversation = " ".join(messages).casefold()
    return set(known) == set(evidence) and all(
        isinstance(span, str) and span.strip() and span.strip().casefold() in conversation for span in evidence.values()
    )


def run(model_name: str, adapter_path: str, max_tokens: int) -> dict:
    first_training_row = json.loads(TRAIN_DATA.read_text(encoding="utf-8").splitlines()[0])
    system_prompt = first_training_row["messages"][0]["content"]
    scenarios = [json.loads(line) for line in SCENARIOS.read_text(encoding="utf-8").splitlines() if line.strip()]
    model, tokenizer = load(model_name, adapter_path=adapter_path)
    outcomes = []
    for scenario in scenarios:
        prompt = tokenizer.apply_chat_template(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": scenario["messages"][-1] + " /no_think"},
            ],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        started = time.perf_counter()
        raw = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            sampler=make_sampler(temp=0.0),
            verbose=False,
        )
        error = None
        try:
            decision = _extract_json(raw)
        except ValueError as exc:
            decision = {}
            error = str(exc)
        contract_valid = _contract_valid(decision)
        evidence_valid = contract_valid and _evidence_valid(decision, scenario["messages"])
        correct = (
            contract_valid
            and decision.get("action") == scenario["expected_action"]
            and decision.get("tool") == scenario["expected_tool"]
        )
        outcomes.append(
            {
                "id": scenario["id"],
                "action": decision.get("action"),
                "tool": decision.get("tool"),
                "correct": correct,
                "contract_valid": contract_valid,
                "evidence_valid": evidence_valid,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "error": error,
                "raw_output": raw if not correct or not evidence_valid else None,
            }
        )
    count = len(outcomes)
    return {
        "model": model_name,
        "adapter_path": adapter_path,
        "scenario_count": count,
        "direct_accuracy": round(sum(item["correct"] for item in outcomes) / count, 4),
        "contract_valid_rate": round(sum(item["contract_valid"] for item in outcomes) / count, 4),
        "evidence_valid_rate": round(sum(item["evidence_valid"] for item in outcomes) / count, 4),
        "mean_latency_seconds": round(sum(item["latency_seconds"] for item in outcomes) / count, 3),
        "failures": [item for item in outcomes if not item["correct"] or not item["evidence_valid"]],
        "outcomes": outcomes,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a local HealthAI Qwen LoRA adapter.")
    parser.add_argument("--model", default="Qwen/Qwen3-0.6B")
    parser.add_argument("--adapter-path", default="backend/finetuning/adapters")
    parser.add_argument("--max-tokens", type=int, default=500)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.model, arguments.adapter_path, arguments.max_tokens), indent=2))
