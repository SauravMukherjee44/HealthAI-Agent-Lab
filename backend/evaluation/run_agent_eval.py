import json
from pathlib import Path

from backend.app.orchestrator import TriageOrchestrator
from backend.app.schemas import Locale
from backend.app.security import TokenCodec

SCENARIOS = Path(__file__).with_name("scenarios.jsonl")


def run(path: Path = SCENARIOS) -> dict:
    orchestrator = TriageOrchestrator(TokenCodec("evaluation-only-secret"))
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes = []
    for record in records:
        response = orchestrator.start(record["message"], Locale(record["locale"]))
        outcomes.append(
            {
                "id": record["id"],
                "status_correct": response.status == record["expected_status"],
                "condition_correct": response.condition == record["expected_condition"],
                "actual_status": response.status,
                "actual_condition": response.condition,
            }
        )
    status_accuracy = sum(item["status_correct"] for item in outcomes) / len(outcomes)
    routing_accuracy = sum(item["condition_correct"] for item in outcomes) / len(outcomes)
    emergency = [
        item for item, record in zip(outcomes, records, strict=True) if record["expected_status"] == "emergency"
    ]
    emergency_recall = sum(item["actual_status"] == "emergency" for item in emergency) / len(emergency)
    return {
        "scenario_count": len(records),
        "status_accuracy": round(status_accuracy, 4),
        "routing_accuracy": round(routing_accuracy, 4),
        "emergency_recall": round(emergency_recall, 4),
        "failures": [item for item in outcomes if not item["status_correct"] or not item["condition_correct"]],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["failures"] else 0)
