import json
import time
from pathlib import Path

from backend.app.config import Settings
from backend.app.qwen_runtime import DockerModelRunner
from backend.app.routing import DecisionPolicyError, DecisionPolicyValidator, HybridRouter, QwenJsonRouter, RulesRouter
from backend.app.tool_registry import SpecialistToolRegistry

SCENARIOS = Path(__file__).with_name("qwen_scenarios.jsonl")


def run(path: Path = SCENARIOS) -> dict:
    settings = Settings()
    registry = SpecialistToolRegistry(settings.artifacts_dir)
    qwen = QwenJsonRouter(DockerModelRunner(settings.qwen_base_url, settings.qwen_model, 60))
    hybrid = HybridRouter(qwen, RulesRouter(registry))
    policy = DecisionPolicyValidator(registry)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes = []
    for record in records:
        started = time.perf_counter()
        error = None
        try:
            direct = qwen.decide(record["messages"])
        except ValueError as exc:
            direct = None
            error = str(exc)
        hybrid_decision = hybrid.decide(record["messages"])
        try:
            policy.validate(hybrid_decision, record["messages"])
            policy_passed = True
        except DecisionPolicyError as exc:
            policy_passed = False
            error = str(exc)
        outcomes.append(
            {
                "id": record["id"],
                "direct_action": direct.action if direct else None,
                "direct_tool": direct.tool if direct else None,
                "hybrid_action": hybrid_decision.action,
                "hybrid_tool": hybrid_decision.tool,
                "correct": hybrid_decision.action == record["expected_action"]
                and hybrid_decision.tool == record["expected_tool"],
                "policy_passed": policy_passed,
                "latency_seconds": round(time.perf_counter() - started, 3),
                "error": error,
            }
        )
    return {
        "model": settings.qwen_model,
        "scenario_count": len(records),
        "hybrid_accuracy": round(sum(item["correct"] for item in outcomes) / len(outcomes), 4),
        "policy_pass_rate": round(sum(item["policy_passed"] for item in outcomes) / len(outcomes), 4),
        "mean_latency_seconds": round(sum(item["latency_seconds"] for item in outcomes) / len(outcomes), 3),
        "direct_qwen_accuracy": round(
            sum(
                item["direct_action"] == record["expected_action"] and item["direct_tool"] == record["expected_tool"]
                for item, record in zip(outcomes, records, strict=True)
            )
            / len(outcomes),
            4,
        ),
        "failures": [item for item in outcomes if not item["correct"] or not item["policy_passed"]],
        "outcomes": outcomes,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
